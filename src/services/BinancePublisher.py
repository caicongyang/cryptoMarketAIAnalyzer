import os
import json
import getpass
import time
import logging
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
    def __init__(self):
        """初始化币安发布器"""
        self.data_path = os.getenv('DATA_SAVE_PATH', './data')
        self.chrome_user_dir = f"C:\\Users\\{getpass.getuser()}\\AppData\\Local\\Google\\Chrome\\User Data"
        logger.info("初始化币安发布器")
        logger.debug("数据路径: %s", self.data_path)
        logger.debug("Chrome用户目录: %s", self.chrome_user_dir)
        
    def push_to_binance(self, content):
        """使用已登录的Chrome推送内容到币安社区"""
        browser = None
        page = None
        try:
            logger.info("开始推送内容到币安社区")
            logger.debug("内容长度: %d 字符", len(content))
            
            with sync_playwright() as p:
                try:
                    logger.info("启动浏览器...")
                    # 使用持久化上下文启动浏览器
                    browser = p.chromium.launch_persistent_context(
                        user_data_dir=self.chrome_user_dir,
                        accept_downloads=True,
                        headless=False,
                        bypass_csp=True,
                        slow_mo=1000,
                        channel="chrome"
                    )
                    logger.info("浏览器启动成功")
                    
                    # 创建新页面
                    page = browser.new_page()
                    logger.info("创建新页面成功")
                    
                    # 访问币安社区
                    logger.info("正在访问币安社区...")
                    page.goto('https://www.binance.com/zh-CN/square')
                    logger.info("页面导航完成")
                     
                    # 等待页面加载
                    logger.info("等待页面初步加载...")
                    page.wait_for_load_state('domcontentloaded')
                    logger.info("页面初步加载完成，等待额外加载时间...")
                    time.sleep(10)  # 额外等待时间，确保页面完全加载
                    logger.info("页面完全加载完成")
                    
                    # 等待输入框加载并填写内容
                    logger.info("等待输入框加载...")
                    editor = page.locator('div.ProseMirror[contenteditable="true"]')
                    try:
                        editor.wait_for(state='visible', timeout=20000)  # 增加超时时间到20秒
                        logger.info("输入框加载成功")
                    except TimeoutError:
                        logger.error("输入框加载超时")
                        raise
                    
                    # 清空输入框
                    logger.info("清空输入框...")
                    editor.evaluate('el => el.innerHTML = ""')
                    logger.info("输入框清空完成")
                    
                    # 输入内容
                    logger.info("开始输入内容...")
                    editor.fill(content)
                    logger.info("内容输入完成")
                    
                    # 等待发文按钮加载并点击
                    logger.info("等待发文按钮...")
                    post_button = page.locator('span[data-bn-type="text"].css-1c82c04:text("发文")')
                    try:
                        post_button.wait_for(state='visible', timeout=20000)  # 增加超时时间到20秒
                        logger.info("发文按钮加载成功，准备点击")
                        post_button.click()
                        logger.info("发文按钮点击完成")
                    except TimeoutError:
                        logger.error("发文按钮加载超时")
                        raise
                    
                    # 等待发文完成
                    logger.info("等待发文完成...")
                    page.wait_for_timeout(3000)
                    logger.info("发文等待时间结束")
                    
                    logger.info("推送成功完成")
                    return {
                        "status": "success",
                        "message": "成功推送到币安社区"
                    }
                    
                except TimeoutError as e:
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
            
            logger.info("开始推送到币安社区...")
            # 推送到币安社区
            return self.push_to_binance(recommendation)
            
        except Exception as e:
            logger.error("推送投资建议时发生错误: %s", str(e))
            return {
                "status": "error",
                "message": f"推送投资建议失败: {str(e)}"
            } 