import os
import json
import logging
import html
import re
from datetime import datetime, timedelta
import requests
from typing import Optional, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("weixin-publisher")

class WeixinToken:
    def __init__(self, access_token: str, expires_in: int):
        self.access_token = access_token
        self.expires_in = expires_in
        self.expires_at = datetime.now() + timedelta(seconds=expires_in)

class ConfigManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ConfigManager()
        return cls._instance

    async def get(self, key: str) -> str:
        return os.getenv(key, '')

class WXPublisher:
    def __init__(self):
        """初始化微信公众号发布器"""
        self.access_token: Optional[WeixinToken] = None
        self.app_id: Optional[str] = None
        self.app_secret: Optional[str] = None
        self.config_manager = ConfigManager.get_instance()
        self.data_path = os.getenv('DATA_SAVE_PATH', './data')

    async def refresh(self) -> None:
        """刷新配置信息"""
        self.app_id = await self.config_manager.get("WEIXIN_APP_ID")
        self.app_secret = await self.config_manager.get("WEIXIN_APP_SECRET")
        logger.info("微信公众号配置: %s", {
            "appId": self.app_id,
            "appSecret": "***" + (self.app_secret[-4:] if self.app_secret else "")  # 只显示密钥后4位
        })

    async def ensure_access_token(self) -> str:
        """确保访问令牌有效"""
        # 检查现有token是否有效
        if (self.access_token and 
            self.access_token.expires_at > datetime.now() + timedelta(minutes=1)):  # 预留1分钟余量
            return self.access_token.access_token

        try:
            await self.refresh()
            # 获取新token
            url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
            response = requests.get(url).json()
            
            if 'access_token' not in response:
                raise Exception(f"获取access_token失败: {json.dumps(response)}")

            self.access_token = WeixinToken(
                response['access_token'],
                response['expires_in']
            )
            return self.access_token.access_token

        except Exception as error:
            logger.error("获取微信access_token失败: %s", error)
            raise

    def _preprocess_article(self, article: str) -> str:
        """预处理文章内容，确保编码正确"""
        if not article:
            return ""
            
        # 确保内容是字符串
        if not isinstance(article, str):
            article = str(article)
            
        # 检查编码，确保是UTF-8
        try:
            # 如果是bytes，转成字符串
            if isinstance(article, bytes):
                article = article.decode('utf-8')
                
            # 确保可以编码为UTF-8，这样可以检测潜在的编码问题
            article.encode('utf-8').decode('utf-8')
        except UnicodeError:
            logger.warning("文章内容编码有问题，尝试修复...")
            # 尝试修复编码问题
            try:
                # 如果是bytes，可能是其他编码，尝试不同的编码
                if isinstance(article, bytes):
                    for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
                        try:
                            article = article.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue
            except Exception as e:
                logger.error(f"修复编码失败: {e}")
        
        # 处理HTML实体和特殊字符编码
        article = html.unescape(article)  # 将HTML实体转换回实际字符
                
        # 移除可能导致问题的特殊字符或控制字符
        article = ''.join(ch for ch in article if ord(ch) >= 32 or ch in '\n\t\r')
        
        # 检查是否存在中文字符 (如果全是英文，可能需要特别处理)
        has_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in article)
        if not has_chinese and len(article) > 50:  # 较长内容中没有中文可能是编码问题
            logger.warning("文章内容中未检测到中文字符，可能存在编码问题")
            
        return article

    def _md_to_html(self, md_content: str) -> str:
        """将Markdown内容转换为HTML"""
        if not md_content:
            return ""
            
        # 基本的Markdown转换
        # 标题转换
        html_content = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', md_content, flags=re.MULTILINE)
        html_content = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^#### (.*?)$', r'<h4>\1</h4>', html_content, flags=re.MULTILINE)
        
        # 粗体和斜体
        html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)
        html_content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html_content)
        
        # 链接
        html_content = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html_content)
        
        # 代码块
        html_content = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', html_content, flags=re.DOTALL)
        
        # 行内代码
        html_content = re.sub(r'`(.*?)`', r'<code>\1</code>', html_content)
        
        # 无序列表
        html_content = re.sub(r'^\* (.*?)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'(<li>.*?</li>)(\n<li>.*?</li>)+', r'<ul>\g<0></ul>', html_content, flags=re.DOTALL)
        
        # 有序列表
        html_content = re.sub(r'^\d+\. (.*?)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'(<li>.*?</li>)(\n<li>.*?</li>)+', r'<ol>\g<0></ol>', html_content, flags=re.DOTALL)
        
        # 段落
        html_content = re.sub(r'(?<!\n)\n(?!\n)', ' ', html_content)  # 单个换行变为空格
        html_content = re.sub(r'\n\n(.*?)(?=\n\n|\Z)', r'<p>\1</p>', html_content, flags=re.DOTALL)
        
        return html_content

    def _apply_template(self, html_content: str, title: str, date: str = None) -> str:
        """应用微信文章模板"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
            
        # 提取第一张图片作为封面（如果有）
        cover_image = ""
        img_match = re.search(r'<img.*?src="(.*?)".*?>', html_content)
        if img_match:
            cover_image = img_match.group(1)
            
        # 基于modern模板的微信文章HTML模板
        template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif;
                    line-height: 1.7;
                    color: #333;
                    background-color: #f8f8f8;
                    padding: 20px;
                }}
                .container {{
                    max-width: 100%;
                    margin: 0 auto;
                    background-color: #fff;
                    padding: 25px;
                    border-radius: 12px;
                    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.1);
                }}
                .article-header {{
                    margin-bottom: 30px;
                    border-bottom: 2px solid #f0f0f0;
                    padding-bottom: 20px;
                }}
                .article-title {{
                    font-size: 24px;
                    font-weight: 700;
                    margin-bottom: 10px;
                    color: #222;
                    line-height: 1.4;
                }}
                .article-meta {{
                    font-size: 14px;
                    color: #888;
                    display: flex;
                    align-items: center;
                }}
                .article-date {{
                    margin-right: 15px;
                }}
                .article-content {{
                    margin-top: 25px;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    margin-top: 30px;
                    margin-bottom: 15px;
                    font-weight: 600;
                    color: #222;
                    line-height: 1.4;
                }}
                h1 {{ font-size: 28px; }}
                h2 {{ font-size: 24px; color: #0066cc; position: relative; padding-left: 15px; }}
                h2:before {{
                    content: "";
                    position: absolute;
                    left: 0;
                    top: 5px;
                    bottom: 5px;
                    width: 5px;
                    background: linear-gradient(to bottom, #0066cc, #3399ff);
                    border-radius: 8px;
                }}
                h3 {{ font-size: 20px; color: #333; }}
                h4 {{ font-size: 18px; color: #555; }}
                p {{
                    margin-bottom: 20px;
                    font-size: 16px;
                }}
                a {{
                    color: #0066cc;
                    text-decoration: none;
                    border-bottom: 1px solid #cce5ff;
                    transition: all 0.3s ease;
                }}
                a:hover {{
                    color: #004499;
                    border-bottom-color: #004499;
                }}
                img {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 8px;
                    margin: 20px 0;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                }}
                ul, ol {{
                    margin-bottom: 25px;
                    padding-left: 25px;
                }}
                li {{
                    margin-bottom: 10px;
                }}
                blockquote {{
                    margin: 20px 0;
                    padding: 15px 20px;
                    background-color: #f5f7f9;
                    border-left: 5px solid #0066cc;
                    font-style: italic;
                    color: #555;
                    border-radius: 0 8px 8px 0;
                }}
                code {{
                    background-color: #f2f4f6;
                    padding: 3px 6px;
                    border-radius: 4px;
                    font-family: Menlo, Monaco, "Courier New", monospace;
                    font-size: 14px;
                    color: #c7254e;
                }}
                pre {{
                    background-color: #f2f4f6;
                    padding: 15px;
                    border-radius: 8px;
                    overflow-x: auto;
                    margin: 20px 0;
                }}
                pre code {{
                    background: none;
                    padding: 0;
                    color: #333;
                    font-size: 14px;
                    line-height: 1.5;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 25px 0;
                    overflow-x: auto;
                    display: block;
                }}
                table, th, td {{
                    border: 1px solid #e0e0e0;
                }}
                th, td {{
                    padding: 12px 15px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f4f6;
                    font-weight: 600;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                .highlight {{
                    background-color: #ffffcc;
                    padding: 2px;
                }}
                .article-footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 2px solid #f0f0f0;
                    font-size: 14px;
                    color: #888;
                    text-align: center;
                }}
                .divider {{
                    height: 1px;
                    background: linear-gradient(to right, transparent, #e0e0e0, transparent);
                    margin: 30px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="article-header">
                    <h1 class="article-title">{title}</h1>
                    <div class="article-meta">
                        <span class="article-date">{date}</span>
                    </div>
                </div>
                
                <div class="article-content">
                    {html_content}
                </div>
                
                <div class="divider"></div>
                
                <div class="article-footer">
                    <p>感谢阅读，欢迎在下方留言和分享您的想法！</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return template

    async def upload_draft(self, article: str, title: str, digest: str, media_id: str) -> Dict[str, str]:
        """上传草稿"""
        token = await self.ensure_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
        
        # 预处理文章内容
        article = self._preprocess_article(article)
        
        # 假设文章内容可能是Markdown格式，尝试转换为HTML并应用模板
        try:
            html_content = self._md_to_html(article)
            article = self._apply_template(html_content, title)
            logger.info("Markdown内容已成功转换为带模板的HTML")
        except Exception as e:
            logger.warning(f"Markdown转换失败，使用原始内容: {e}")
        
        # 预处理标题和摘要
        if title and isinstance(title, str):
            title = self._preprocess_article(title)
        if digest and isinstance(digest, str):
            digest = self._preprocess_article(digest)

        articles = [{
            "title": title,
            "author": await self.config_manager.get("AUTHOR"),
            "digest": digest,
            "content": article,
            "thumb_media_id": media_id,
            "need_open_comment": 1 if await self.config_manager.get("NEED_OPEN_COMMENT") == "true" else 0,
            "only_fans_can_comment": 1 if await self.config_manager.get("ONLY_FANS_CAN_COMMENT") == "true" else 0
        }]

        try:
            # 记录请求日志
            logger.debug("微信草稿请求内容: %s", json.dumps({"articles": articles}, ensure_ascii=False))
            
            # 准备请求数据和头信息
            data = json.dumps({"articles": articles}, ensure_ascii=False, separators=(',', ':'))
            headers = {
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json; charset=utf-8'
            }
            
            # 明确指定编码方式进行POST请求
            response = requests.post(
                url, 
                data=data.encode('utf-8'), 
                headers=headers
            )
            
            # 确保响应是UTF-8编码
            if response.encoding.lower() != 'utf-8':
                response.encoding = 'utf-8'
                
            response_json = response.json()
            
            # 记录响应日志
            logger.debug("微信草稿响应内容: %s", json.dumps(response_json, ensure_ascii=False))
            
            if 'errcode' in response_json:
                raise Exception(f"上传草稿失败: {response_json['errmsg']}")

            return {"media_id": response_json['media_id']}

        except Exception as error:
            logger.error("上传微信草稿失败: %s", error)
            raise

    async def upload_image(self, image_url: str) -> str:
        """上传图片到微信"""
        if not image_url:
            return "SwCSRjrdGJNaWioRQUHzgF68BHFkSlb_f5xlTquvsOSA6Yy0ZRjFo0aW9eS3JJu_"

        image_content = requests.get(image_url).content
        token = await self.ensure_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"

        try:
            files = {
                'media': ('image.jpg', image_content, 'image/jpeg')
            }
            response = requests.post(url, files=files).json()

            if 'errcode' in response:
                raise Exception(f"上传图片失败: {response['errmsg']}")

            return response['media_id']

        except Exception as error:
            logger.error("上传微信图片失败: %s", error)
            raise

    async def upload_content_image(self, image_url: str, image_buffer: Optional[bytes] = None) -> str:
        """上传图文消息内的图片获取URL"""
        if not image_url:
            raise Exception("图片URL不能为空")

        token = await self.ensure_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={token}"

        try:
            if image_buffer:
                image_content = image_buffer
            else:
                image_content = requests.get(image_url).content

            files = {
                'media': ('image.jpg', image_content, 'image/jpeg')
            }
            response = requests.post(url, files=files).json()

            if 'errcode' in response:
                raise Exception(f"上传图文消息图片失败: {response['errmsg']}")

            return response['url']

        except Exception as error:
            logger.error("上传微信图文消息图片失败: %s", error)
            raise

    async def publish(self, article: str, title: str, digest: str, media_id: str) -> Dict[str, Any]:
        """发布文章到微信"""
        try:
            # 记录原始内容长度，用于调试
            article_len = len(article) if article else 0
            logger.info(f"原始文章内容长度: {article_len} 字符")
            
            # 预处理文章内容
            article = self._preprocess_article(article)
            
            # 记录处理后内容长度
            processed_len = len(article) if article else 0
            logger.info(f"处理后文章内容长度: {processed_len} 字符")
            
            if processed_len > 0 and processed_len < article_len:
                logger.warning(f"文章内容在预处理中被截断，原始长度: {article_len}，处理后长度: {processed_len}")
            
            # 记录请求详情，但限制内容长度，避免日志过大
            content_preview = article[:200] + "..." if len(article) > 200 else article
            logger.info(f"发布标题: {title}")
            logger.info(f"发布摘要: {digest}")
            logger.info(f"发布图片ID: {media_id}")
            logger.info(f"发布文章预览: {content_preview}")
            
            # 检查是否需要直接发布
            direct_publish = await self.config_manager.get("DIRECT_PUBLISH")
            
            # 上传草稿
            draft = await self.upload_draft(article, title, digest, media_id)
            logger.info(f"草稿上传成功，media_id: {draft['media_id']}")
            
            # 如果配置了直接发布，则调用发布接口
            if direct_publish and direct_publish.lower() == "true":
                publish_result = await self.direct_publish(draft['media_id'])
                logger.info(f"直接发布成功，publish_id: {publish_result['publish_id']}")
                return {
                    "publishId": publish_result['publish_id'],
                    "draftId": draft['media_id'],
                    "status": "publishing",
                    "publishedAt": datetime.now().isoformat(),
                    "platform": "weixin",
                    "url": f"https://mp.weixin.qq.com/s/{draft['media_id']}"
                }
            
            return {
                "publishId": draft['media_id'],
                "status": "draft",
                "publishedAt": datetime.now().isoformat(),
                "platform": "weixin",
                "url": f"https://mp.weixin.qq.com/s/{draft['media_id']}"
            }

        except Exception as error:
            logger.error("微信发布失败: %s", error)
            raise

    async def direct_publish(self, media_id: str) -> Dict[str, Any]:
        """直接发布草稿
        
        Args:
            media_id: 草稿的media_id
            
        Returns:
            Dict: 包含发布ID的字典
        """
        try:
            token = await self.ensure_access_token()
            url = f"https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token={token}"
            
            data = {
                "media_id": media_id
            }
            
            # 准备请求数据和头信息
            data_json = json.dumps(data, ensure_ascii=False)
            headers = {
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json; charset=utf-8'
            }
            
            # 发送请求
            response = requests.post(
                url, 
                data=data_json.encode('utf-8'), 
                headers=headers
            )
            
            # 确保响应是UTF-8编码
            if response.encoding.lower() != 'utf-8':
                response.encoding = 'utf-8'
                
            response_json = response.json()
            
            # 记录响应日志
            logger.debug("微信发布响应内容: %s", json.dumps(response_json, ensure_ascii=False))
            
            if 'errcode' in response_json and response_json['errcode'] != 0:
                error_msg = response_json.get('errmsg', '未知错误')
                error_code = response_json.get('errcode', -1)
                
                # 特殊错误码处理
                if error_code == 53503:
                    error_msg = "该草稿未通过发布检查"
                elif error_code == 53504:
                    error_msg = "需前往公众平台官网使用草稿"
                elif error_code == 53505:
                    error_msg = "请手动保存成功后再发表"
                
                raise Exception(f"发布失败 (错误码: {error_code}): {error_msg}")

            return {
                "publish_id": response_json.get('publish_id', ''),
                "msg_data_id": response_json.get('msg_data_id', '')
            }

        except Exception as error:
            logger.error("直接发布微信文章失败: %s", error)
            raise
            
    async def check_publish_status(self, publish_id: str) -> Dict[str, Any]:
        """查询发布状态
        
        Args:
            publish_id: 发布任务的ID
            
        Returns:
            Dict: 包含发布状态的字典
        """
        try:
            token = await self.ensure_access_token()
            url = f"https://api.weixin.qq.com/cgi-bin/freepublish/get?access_token={token}"
            
            data = {
                "publish_id": publish_id
            }
            
            # 准备请求数据和头信息
            data_json = json.dumps(data, ensure_ascii=False)
            headers = {
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json; charset=utf-8'
            }
            
            # 发送请求
            response = requests.post(
                url, 
                data=data_json.encode('utf-8'), 
                headers=headers
            )
            
            # 确保响应是UTF-8编码
            if response.encoding.lower() != 'utf-8':
                response.encoding = 'utf-8'
                
            response_json = response.json()
            
            # 记录响应日志
            logger.debug("微信发布状态查询响应: %s", json.dumps(response_json, ensure_ascii=False))
            
            if 'errcode' in response_json and response_json['errcode'] != 0:
                raise Exception(f"查询发布状态失败: {response_json['errmsg']}")

            # 可能的发布状态：0=成功, 1=发布中, 2=原创失败, 3=常规失败, 4=平台审核不通过, 5=成功但是转义了表情
            status_map = {
                0: "published",
                1: "publishing",
                2: "failed_original",
                3: "failed_general", 
                4: "failed_audit",
                5: "published_emoji_escaped"
            }
            
            publish_status = response_json.get('publish_status', -1)
            
            return {
                "status": status_map.get(publish_status, "unknown"),
                "publish_id": publish_id,
                "publish_status": publish_status,
                "article_id": response_json.get('article_id', ''),
                "article_url": response_json.get('article_url', ''),
                "fail_reason": response_json.get('fail_reason', '')
            }

        except Exception as error:
            logger.error("查询微信发布状态失败: %s", error)
            raise

    async def validate_ip_whitelist(self) -> str | bool:
        """验证当前服务器IP是否在微信公众号的IP白名单中"""
        try:
            await self.ensure_access_token()
            return True
        except Exception as error:
            error_msg = str(error)
            if "40164" in error_msg:
                import re
                match = re.search(r"invalid ip ([^ ]+)", error_msg)
                return match.group(1) if match else "未知IP"
            raise

    async def push_recommendation(self) -> Dict[str, Any]:
        """推送最新的投资建议到微信公众号"""
        try:
            # 读取最新的投资建议
            recommendation_path = os.path.join(self.data_path, "investment_recommendation.json")
            
            try:
                with open(recommendation_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"成功读取投资建议文件: {recommendation_path}")
            except FileNotFoundError:
                logger.error(f"未找到投资建议文件: {recommendation_path}")
                return {
                    "status": "error",
                    "message": "未找到投资建议文件"
                }
            except json.JSONDecodeError:
                logger.error(f"投资建议文件格式错误: {recommendation_path}")
                return {
                    "status": "error",
                    "message": "投资建议文件格式错误"
                }
            
            # 获取必要的字段
            content = data.get('recommendation', '')
            title = data.get('title', '投资建议分析报告')
            digest = data.get('digest', '投资建议分析报告')
            image_url = data.get('image_url', '')
            
            # 检查内容是否为空
            if not content:
                logger.error("投资建议内容为空")
                return {
                    "status": "error",
                    "message": "投资建议内容为空"
                }
            
            # 预处理内容和字段
            content = self._preprocess_article(content)
            title = self._preprocess_article(title)
            digest = self._preprocess_article(digest)
            
            # 记录处理结果
            logger.info(f"处理后标题: {title}")
            logger.info(f"处理后摘要: {digest}")
            logger.info(f"处理后内容长度: {len(content)} 字符")
            
            # 上传图片
            logger.info(f"准备上传图片: {image_url}")
            media_id = await self.upload_image("https://gips0.baidu.com/it/u=1690853528,2506870245&fm=3028&app=3028&f=JPEG&fmt=auto?w=1024&h=1024")
            logger.info(f"上传图片成功: {media_id}")
            
            # 推送到微信公众号
            logger.info("开始推送到微信公众号...")
            result = await self.publish(
                article=content,
                title=title,
                digest=digest,
                media_id=media_id
            )
            logger.info(f"推送结果: {json.dumps(result, ensure_ascii=False)}")
            return result
            
        except Exception as error:
            logger.error("推送投资建议时发生错误: %s", error)
            return {
                "status": "error",
                "message": f"推送投资建议失败: {str(error)}"
            } 