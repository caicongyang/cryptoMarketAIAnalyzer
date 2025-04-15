import os
import json
import logging
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

    async def upload_draft(self, article: str, title: str, digest: str, media_id: str) -> Dict[str, str]:
        """上传草稿"""
        token = await self.ensure_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"

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
            response = requests.post(url, json={"articles": articles}).json()
            
            if 'errcode' in response:
                raise Exception(f"上传草稿失败: {response['errmsg']}")

            return {"media_id": response['media_id']}

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
            logger.info(f"发布文章: {article}")
            logger.info(f"发布标题: {title}")
            logger.info(f"发布摘要: {digest}")
            logger.info(f"发布图片: {media_id}")
            draft = await self.upload_draft(article, title, digest, media_id)
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
            except FileNotFoundError:
                return {
                    "status": "error",
                    "message": "未找到投资建议文件"
                }
            except json.JSONDecodeError:
                return {
                    "status": "error",
                    "message": "投资建议文件格式错误"
                }
            
            # 获取必要的字段
            content = data.get('recommendation', '')
            title = data.get('title', '投资建议分析报告')
            digest = data.get('digest', '投资建议分析报告')
            image_url = data.get('image_url', '')
            
            if not content:
                return {
                    "status": "error",
                    "message": "投资建议内容为空"
                }
            
            logger.info(f"上传图片: {image_url}")
            # 上传图片
            media_id = await self.upload_image("https://gips0.baidu.com/it/u=1690853528,2506870245&fm=3028&app=3028&f=JPEG&fmt=auto?w=1024&h=1024")
            logger.info(f"上传图片成功: {media_id}")
            # 推送到微信公众号
            return await self.publish(
                article=content,
                title=title,
                digest=digest,
                media_id=media_id
            )
            
        except Exception as error:
            logger.error("推送投资建议时发生错误: %s", error)
            return {
                "status": "error",
                "message": f"推送投资建议失败: {str(error)}"
            } 