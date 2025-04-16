import os
import json
import getpass
import time
import html
import logging
import signal
import psutil
import platform
import subprocess
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("binance-publisher")

class BinancePublisher:
    def __init__(self, profile_name="Default"):
        """初始化币安发布器"""
        self.data_path = os.getenv('DATA_SAVE_PATH', './data')
        username = getpass.getuser()
        
        # 根据系统设置正确的Chrome用户数据路径
        if platform.system() == "Darwin":  # macOS
            self.chrome_user_dir = f"/Users/{username}/Library/Application Support/Google/Chrome/User Data"
        elif platform.system() == "Windows":  # Windows
            self.chrome_user_dir = f"C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data"
        else:  # Linux等其他系统
            self.chrome_user_dir = f"/home/{username}/.config/google-chrome"
            
        self.profile_name = profile_name  # 添加配置文件名称参数
        
        # 确保数据目录存在
        os.makedirs(self.data_path, exist_ok=True)
        
        logger.info("初始化币安发布器")
        logger.debug("数据路径: %s", self.data_path)
        logger.debug("Chrome用户目录: %s", self.chrome_user_dir)
        logger.debug("使用的配置文件: %s", self.profile_name)
        logger.debug("当前操作系统: %s", platform.system())
        
    def push_to_binance(self, content):
        """使用已登录的Chrome推送内容到币安社区"""
        # 预处理内容
        content = self._preprocess_content(content)
        
        browser = None
        page = None
        try:
            logger.info("开始推送内容到币安社区")
            logger.debug("内容长度: %d 字符", len(content))
            
            # 首先检查Chrome是否已经运行
            is_chrome_running = self._is_chrome_running()
            logger.info(f"Chrome运行状态检查: {'运行中' if is_chrome_running else '未运行'}")
            
            # 尝试关闭所有Chrome进程以避免冲突
            if is_chrome_running:
                logger.info("尝试关闭所有Chrome进程...")
                if self._close_all_chrome_instances():
                    logger.info("成功关闭Chrome进程")
                else:
                    logger.warning("无法完全关闭Chrome进程，可能会影响登录状态获取")
            
            with sync_playwright() as p:
                try:
                    logger.info("启动浏览器...")
                    
                    # 构建Profile路径
                    user_data_dir = os.path.join(self.chrome_user_dir)
                    profile_path = os.path.join(user_data_dir, self.profile_name)
                    
                    if not os.path.exists(profile_path):
                        logger.warning(f"Profile目录不存在: {profile_path}，尝试使用默认Profile")
                        profile_path = os.path.join(user_data_dir, "Default")
                    
                    if not os.path.exists(profile_path):
                        logger.warning(f"默认Profile目录也不存在，使用整个用户数据目录")
                        profile_path = user_data_dir
                    
                    logger.info(f"使用配置文件路径: {profile_path}")
                    
                    # 使用原生Chrome启动，指定用户数据目录，保留现有会话
                    browser = p.chromium.launch_persistent_context(
                        user_data_dir=profile_path,
                        headless=False,
                        slow_mo=500,
                        channel="chrome",
                        accept_downloads=True,
                        ignore_default_args=["--disable-extensions"],
                        args=[
                            "--no-sandbox",
                            "--disable-web-security", 
                            "--disable-features=IsolateOrigins,site-per-process"
                        ],
                        viewport={"width": 1280, "height": 800}
                    )
                    logger.info("浏览器启动成功")
                    
                    # 创建新页面
                    page = browser.new_page()
                    logger.info("创建新页面成功")
                    
                    # 访问币安社区
                    logger.info("正在访问币安社区...")
                    page.goto('https://www.binance.com/zh-CN/square', wait_until="networkidle", timeout=60000)
                    logger.info("页面导航完成")
                    
                    # 保存屏幕截图以便调试
                    self._save_debug_screenshot(page, "page_loaded")
                    
                    # 等待页面加载
                    logger.info("等待页面初步加载...")
                    page.wait_for_load_state('networkidle')  # 改为等待网络空闲
                    logger.info("页面初步加载完成，等待额外加载时间...")
                    time.sleep(20)  # 额外等待时间，确保页面完全加载
                    logger.info("页面完全加载完成")
                    
                    # 检查是否已登录
                    logger.info("检查是否已登录...")
                    if not self._check_login_status(page):
                        self._save_debug_screenshot(page, "not_logged_in")
                        logger.error("用户未登录或登录状态无法访问")
                        return {
                            "status": "error",
                            "message": "用户未登录，请先在Chrome浏览器中登录币安账号"
                        }
                    
                    logger.info("检测到用户已登录")
                    self._save_debug_screenshot(page, "logged_in")
                    
                    # 等待输入框加载并填写内容
                    logger.info("等待输入框加载...")
                    editor = page.locator('div.ProseMirror[contenteditable="true"]')
                    try:
                        editor.wait_for(state='visible', timeout=30000)  # 增加超时时间到30秒
                        logger.info("输入框加载成功")
                        self._save_debug_screenshot(page, "editor_found")
                    except PlaywrightTimeoutError:
                        logger.error("输入框加载超时")
                        self._save_debug_screenshot(page, "editor_timeout")
                        raise
                    
                    # 清空输入框
                    logger.info("清空输入框...")
                    editor.evaluate('el => el.innerHTML = ""')
                    logger.info("输入框清空完成")
                    
                    # 输入内容
                    logger.info("开始输入内容...")
                    # 先确保内容是UTF-8编码的字符串
                    if isinstance(content, bytes):
                        content = content.decode('utf-8')
                    
                    # 记录部分内容预览用于调试
                    content_preview = content[:200] + "..." if len(content) > 200 else content
                    logger.debug(f"内容预览: {content_preview}")
                    
                    # 通过JavaScript设置内容，避免直接输入可能导致的编码问题
                    logger.info("通过JavaScript设置内容...")
                    editor.evaluate(f'el => el.innerHTML = {json.dumps(content)}')
                    # 完成后点击一下编辑区，确保内容被接受
                    editor.click()
                    
                    # 使用type方法备用，如果上述方法失败
                    if not editor.evaluate('el => el.textContent.length > 0'):
                        logger.warning("JavaScript设置内容失败，使用type方法尝试...")
                        editor.type(content)
                    
                    logger.info("内容输入完成")
                    self._save_debug_screenshot(page, "content_entered")
                    
                    # 等待发文按钮加载并点击
                    logger.info("等待发文按钮...")
                    post_button = page.locator('span[data-bn-type="text"].css-1c82c04:text("发文")')
                    try:
                        post_button.wait_for(state='visible', timeout=30000)  # 增加超时时间到30秒
                        logger.info("发文按钮加载成功，准备点击")
                        self._save_debug_screenshot(page, "before_post_click")
                        post_button.click()
                        logger.info("发文按钮点击完成")
                    except PlaywrightTimeoutError:
                        logger.error("发文按钮加载超时")
                        self._save_debug_screenshot(page, "post_button_timeout")
                        raise
                    
                    # 等待发文完成
                    logger.info("等待发文完成...")
                    page.wait_for_timeout(5000)
                    logger.info("发文等待时间结束")
                    self._save_debug_screenshot(page, "post_completed")
                    
                    logger.info("推送成功完成")
                    return {
                        "status": "success",
                        "message": "成功推送到币安社区"
                    }
                    
                except PlaywrightTimeoutError as e:
                    logger.error("页面元素等待超时: %s", str(e))
                    screenshot_path = self._save_error_screenshot(page)
                    return {
                        "status": "error",
                        "message": f"页面元素等待超时: {str(e)}",
                        "screenshot": screenshot_path
                    }
                    
                except Exception as e:
                    logger.error("推送过程出错: %s", str(e))
                    screenshot_path = self._save_error_screenshot(page)
                    return {
                        "status": "error",
                        "message": f"推送失败: {str(e)}",
                        "screenshot": screenshot_path
                    }
                    
                finally:
                    if browser:
                        logger.info("正在关闭浏览器...")
                        try:
                            browser.close()
                            logger.info("浏览器关闭成功")
                        except Exception as e:
                            logger.error("关闭浏览器时出错: %s", str(e))
            
        except Exception as e:
            logger.error("连接浏览器失败: %s", str(e))
            return {
                "status": "error",
                "message": f"连接浏览器失败: {str(e)}"
            }

    def _is_chrome_running(self):
        """检查Chrome是否正在运行"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if 'chrome' in proc.info['name'].lower() or 'google chrome' in proc.info['name'].lower():
                    return True
            return False
        except Exception as e:
            logger.error(f"检查Chrome运行状态失败: {e}")
            return False
            
    def _close_all_chrome_instances(self):
        """尝试关闭所有Chrome实例"""
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run(['pkill', '-9', 'Google Chrome'], shell=True, check=False)
                subprocess.run(['pkill', '-9', 'Chrome'], shell=True, check=False)
            elif platform.system() == "Windows":
                subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], shell=True, check=False)
            else:  # Linux等
                subprocess.run(['pkill', '-9', 'chrome'], shell=True, check=False)
                
            # 等待进程真正结束
            time.sleep(2)
            
            # 再次检查是否所有Chrome都已关闭
            return not self._is_chrome_running()
        except Exception as e:
            logger.error(f"关闭Chrome进程失败: {e}")
            return False

    def _check_login_status(self, page):
        """检查是否已登录币安账号"""
        try:
            # 获取页面HTML用于调试
            html_content = page.content()
            login_indicators = ["请登录", "登录", "login", "sign in"]
            for indicator in login_indicators:
                if indicator.lower() in html_content.lower():
                    logger.warning(f"在页面内容中发现登录提示: {indicator}")
            
            # 尝试查找登录元素 - 多种可能的选择器
            login_selectors = [
                'button:has-text("登录")',
                'a:has-text("登录")',
                'div:has-text("登录"):not(:has(*))',  # 没有子元素的登录文本
                '[href*="login"]'
            ]
            
            for selector in login_selectors:
                elements = page.locator(selector)
                if elements.count() > 0 and elements.first.is_visible():
                    logger.warning(f"检测到登录按钮: {selector}")
                    return False
            
            # 尝试查找用户头像或个人中心元素 - 多种可能的选择器
            logged_in_selectors = [
                'div.css-1hsz9t1',
                '.UserAvatar',
                'a:has-text("个人中心")',
                '[href*="my"]',
                'img.avatar',
                'div.user-info',
                '[data-testid="header-user-icon"]'
            ]
            
            for selector in logged_in_selectors:
                elements = page.locator(selector)
                if elements.count() > 0 and elements.first.is_visible():
                    logger.info(f"检测到用户已登录: {selector}")
                    return True
                    
            # 特别检查是否可以找到编辑器元素（仅登录用户可见）
            editor = page.locator('div.ProseMirror[contenteditable="true"]')
            if editor.count() > 0:
                logger.info("检测到编辑器元素，用户已登录")
                return True
                
            # 查看页面标题或URL
            page_title = page.title()
            current_url = page.url
            
            if "登录" in page_title or "login" in current_url.lower():
                logger.warning("页面标题或URL包含登录相关字样，可能未登录")
                return False
                
            # 如果没有明确发现未登录标志，并且找到了内容输入区域，我们可以假设用户已登录
            content_area = page.locator('.feed-publish-wrapper, .post-editor, div.dynamic-form')
            if content_area.count() > 0 and content_area.first.is_visible():
                logger.info("发现内容发布区域，用户可能已登录")
                return True
                
            logger.warning("无法确定登录状态，假设未登录")
            return False
                
        except Exception as e:
            logger.error(f"检查登录状态出错: {e}")
            return False
            
    def _save_debug_screenshot(self, page, tag):
        """保存带有标记的调试截图"""
        if not page:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(self.data_path, f'debug_{tag}_{timestamp}.png')
            page.screenshot(path=screenshot_path)
            logger.debug(f"调试截图已保存: {screenshot_path}")
        except Exception as e:
            logger.error(f"保存调试截图失败: {e}")

    def _save_error_screenshot(self, page) -> str:
        """保存错误截图"""
        if not page:
            logger.warning("无法保存截图：页面对象为空")
            return ""
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(self.data_path, f'error_screenshot_{timestamp}.png')
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("错误截图已保存: %s", screenshot_path)
            return screenshot_path
        except Exception as e:
            logger.error("保存错误截图失败: %s", str(e))
            return ""

    def _preprocess_content(self, content):
        """预处理内容，确保编码正确"""
        if not content:
            return ""
            
        # 确保内容是字符串
        if not isinstance(content, str):
            content = str(content)
        
        # 如果是bytes，转换为字符串
        if isinstance(content, bytes):
            try:
                content = content.decode('utf-8')
            except UnicodeDecodeError:
                # 尝试不同的编码
                for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
                    try:
                        content = content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
        
        # 处理HTML实体和特殊字符编码
        content = html.unescape(content)  # 将HTML实体转换回实际字符
        
        # 移除可能导致问题的特殊字符或控制字符
        content = ''.join(ch for ch in content if ord(ch) >= 32 or ch in '\n\t\r')
        
        # 检查是否存在中文字符 (如果全是英文，可能需要特别处理)
        has_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in content)
        if not has_chinese and len(content) > 50:  # 较长内容中没有中文可能是编码问题
            logger.warning("内容中未检测到中文字符，可能存在编码问题")
        
        return content

    def push_recommendation(self):
        """推送最新的投资建议到币安社区"""
        try:
            logger.info("开始推送投资建议")
            # 读取最新的投资建议
            recommendation_path = os.path.join(self.data_path, "investment_recommendation.json")
            
            try:
                logger.info("读取投资建议文件: %s", recommendation_path)
                with open(recommendation_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    recommendation = data.get('recommendation', '')
                    # 确保内容是字符串类型
                    if not isinstance(recommendation, str):
                        recommendation = str(recommendation)
                logger.info("投资建议文件读取成功")
            except FileNotFoundError:
                logger.error("未找到投资建议文件: %s", recommendation_path)
                return {
                    "status": "error",
                    "message": "未找到投资建议文件"
                }
            except json.JSONDecodeError:
                logger.error("投资建议文件格式错误: %s", recommendation_path)
                return {
                    "status": "error",
                    "message": "投资建议文件格式错误"
                }
            
            if not recommendation:
                logger.error("投资建议内容为空")
                return {
                    "status": "error",
                    "message": "投资建议内容为空"
                }
            
            # 预处理推荐内容
            recommendation = self._preprocess_content(recommendation)
            
            logger.info("开始推送到币安社区...")
            # 推送到币安社区
            return self.push_to_binance(recommendation)
            
        except Exception as e:
            logger.error("推送投资建议时发生错误: %s", str(e))
            return {
                "status": "error",
                "message": f"推送投资建议失败: {str(e)}"
            } 