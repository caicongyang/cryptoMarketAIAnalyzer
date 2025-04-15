from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from bs4 import BeautifulSoup
import time
import sys
import subprocess
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# 设置默认编码为UTF-8
if sys.platform == 'win32':
    import locale
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

load_dotenv()

class FinancialDataCrawler:
    def __init__(self):
        self.data_path = os.getenv('DATA_SAVE_PATH', './data')
        os.makedirs(self.data_path, exist_ok=True)
        self.cmc_url = "https://coinmarketcap.com/community/topics/BTC%20Price%20Analysis%23/latest/"
        self.articles_url = "https://coinmarketcap.com/community/articles/"
        self._ensure_playwright_browsers()
        self.max_retries = 3
        self.timeout = 60000  # 增加超时时间到60秒

    def _ensure_playwright_browsers(self):
        """确保Playwright浏览器已安装"""
        try:
            result = subprocess.run(
                ['python', '-m', 'playwright', 'install', 'chromium'],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print("使用python -m playwright install失败，尝试其他方式...")
                result = subprocess.run(
                    ['playwright', 'install', 'chromium'],
                    capture_output=True,
                    text=True
                )
            if result.returncode != 0:
                print("警告：Playwright浏览器安装可能失败，但仍将尝试继续...")
        except Exception as e:
            print(f"Playwright浏览器安装过程中出错: {e}")
            print("将尝试使用系统默认浏览器...")

    def wait_for_page_load(self, page):
        """等待页面加载完成"""
        try:
            # 等待页面加载
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            # 等待主要内容加载
            page.wait_for_selector("div[class*='post-content']", timeout=self.timeout)
            # 额外等待以确保动态内容加载
            time.sleep(5)
        except PlaywrightTimeoutError:
            print("页面加载超时，但将继续尝试获取内容...")

    def scroll_until_enough_posts(self, page, target_count=20):
        """滚动直到获取足够数量的帖子或没有更多内容"""
        try:
            # 获取初始帖子数量
            post_elements = page.query_selector_all("div[class*='post-content']")
            current_count = len(post_elements)
            print(f"初始加载了 {current_count} 条帖子")
            
            # 记录最后一个帖子的data-index
            last_index = None
            if post_elements:
                last_post = post_elements[-1]
                last_index = last_post.get_attribute("data-index")
            
            # 如果初始数量不足，尝试滚动加载
            while current_count < target_count:
                # 滚动到底部
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(10)  # 增加等待时间到10秒
                
                # 等待新内容加载
                try:
                    # 等待新帖子出现（通过data-index判断）
                    page.wait_for_function("""
                        () => {
                            const posts = document.querySelectorAll("div[class*='post-content']");
                            if (posts.length === 0) return false;
                            
                            const lastPost = posts[posts.length - 1];
                            const currentIndex = lastPost.getAttribute('data-index');
                            
                            return currentIndex !== arguments[0];
                        }
                    """, last_index, timeout=10000)
                except PlaywrightTimeoutError:
                    print("等待新内容加载超时")
                    break
                
                # 获取所有帖子
                new_elements = page.query_selector_all("div[class*='post-content']")
                new_count = len(new_elements)
                
                if new_count > current_count:
                    print(f"加载了 {new_count - current_count} 条新帖子")
                    current_count = new_count
                    post_elements = new_elements
                    
                    # 更新最后一个帖子的data-index
                    last_post = post_elements[-1]
                    last_index = last_post.get_attribute("data-index")
                    print(f"last_index {last_index}")
                    
                    # 确保新加载的内容完全渲染
                    time.sleep(2)
                    
                    # 检查新加载的帖子是否有内容
                    for i in range(current_count - new_count):
                        new_post = post_elements[-(i+1)]
                        content = new_post.inner_text().strip()
                        if not content:
                            print(f"新加载的第 {i+1} 条帖子内容为空，等待更长时间...")
                            time.sleep(3)
                            content = new_post.inner_text().strip()
                            if not content:
                                print("内容仍然为空，可能加载失败")
                else:
                    print("没有更多内容可加载")
                    break
                
                # 等待新内容完全加载
                time.sleep(3)
            
            # 返回前10条或所有可用的帖子
            return post_elements[:target_count]
        except Exception as e:
            print(f"滚动加载时出错: {e}")
            return page.query_selector_all("div[class*='post-content']")[:target_count]

    def process_single_post(self, page, post, post_index):
        """处理单条帖子"""
        try:
            # 1. 获取帖子基本信息
            post_id = post.get_attribute("data-post-id")
            post_time = post.get_attribute("data-post-time")
            
            print(f"\n开始处理帖子 {post_id} (索引: {post_index})")
            
            # 2. 获取作者信息
            author_element = post.query_selector("span.name-text.name-text_username")
            author = author_element.inner_text() if author_element else "Unknown"
            
            avatar_element = post.query_selector("img.avatar-item-img")
            avatar_url = avatar_element.get_attribute("src") if avatar_element else None
            
            print(f"作者: {author}")
            
            # 3. 获取帖子内容
            content_element = post.query_selector("div.text-wrapper")
            content = content_element.inner_text().strip() if content_element else ""
            
            # 获取图片
            images = []
            image_elements = post.query_selector_all("img.post-img")
            for img in image_elements:
                img_url = img.get_attribute("src")
                if img_url:
                    images.append(img_url)
            
            # 获取标签
            tags = []
            tag_elements = post.query_selector_all("a.real-link")
            for tag in tag_elements:
                tag_text = tag.inner_text().strip()
                if tag_text.startswith("#"):
                    tags.append(tag_text)
            
            print(f"内容长度: {len(content)} 字符")
            print(f"图片数量: {len(images)}")
            print(f"标签数量: {len(tags)}")
            
            # 4. 获取互动数据
            views_element = post.query_selector("span.count")
            views = views_element.inner_text() if views_element else "0"
            
            comments_element = post.query_selector("span.count[data-test='post-comment-icon']")
            comments = comments_element.inner_text() if comments_element else "0"
            
            emojis = {}
            emoji_elements = post.query_selector_all("div.emoji-list-item")
            for emoji in emoji_elements:
                emoji_type = emoji.get_attribute("class").split()[-1]
                count = emoji.query_selector("span").inner_text()
                emojis[emoji_type] = count
            
            print(f"浏览量: {views}")
            print(f"评论数: {comments}")
            print(f"表情数据: {emojis}")
            
            # 5. 处理Read all按钮
            read_all_button = post.query_selector("span.read-all")
            if read_all_button:
                print("发现Read all按钮，点击展开完整内容...")
                try:
                    read_all_button.click()
                    time.sleep(3)
                    
                    # 重新获取内容
                    content_element = post.query_selector("div.text-wrapper")
                    if content_element:
                        new_content = content_element.inner_text().strip()
                        print("Read all new_content{}",new_content)
                        if new_content and len(new_content) != len(content):
                            content = new_content
                            print("成功获取完整内容")
                except Exception as e:
                    print(f"点击Read all按钮失败: {e}")
            
            # 6. 整理数据
            post_data = {
                "post_id": post_id,
                "index": post_index,
                "time": post_time,
                "author": {
                    "username": author,
                    "avatar": avatar_url
                },
                "content": {
                    "text": content,
                    "images": images,
                    "tags": tags
                },
                "interaction": {
                    "views": views,
                    "comments": comments,
                    "emojis": emojis
                },
                "crawl_time": datetime.now().isoformat()
            }
            
            # 7. 保存数据
            self.save_data([post_data], "cmc_btc_analysis.json")
            print(f"成功保存帖子 {post_id} 的数据")
            
            return post_data
            
        except Exception as e:
            print(f"处理帖子时出错: {e}")
            return None

    def crawl_market_news(self):
        """爬取市场新闻数据"""
        posts = []
        retry_count = 0
        target_count = 20  # 目标获取的帖子数量
        
        while retry_count < self.max_retries:
            try:
                with sync_playwright() as p:
                    try:
                        browser = p.chromium.launch(
                            headless=False,
                            args=['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
                        )
                    except Exception as e:
                        print(f"启动Chromium失败，尝试使用Firefox: {e}")
                        browser = p.firefox.launch(
                            headless=False,
                            args=['--disable-gpu']
                        )
                    
                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
                    )
                    page = context.new_page()
                    
                    try:
                        print(f"正在访问CoinMarketCap社区... (尝试 {retry_count + 1}/{self.max_retries})")
                        
                        # 设置页面超时
                        page.set_default_timeout(self.timeout)
                        
                        # 访问页面
                        page.goto(self.cmc_url, wait_until="domcontentloaded")
                        
                        # 等待页面加载
                        self.wait_for_page_load(page)
                        
                        # 获取初始帖子
                        virtual_items = page.query_selector_all("div[data-test='virtual-item']")
                        if not virtual_items:
                            raise Exception("未找到任何帖子内容")
                        
                        print(f"初始加载了 {len(virtual_items)} 条帖子")
                        
                        # 处理已加载的帖子
                        for i, virtual_item in enumerate(virtual_items, 1):
                            # 获取帖子索引
                            post_index = virtual_item.get_attribute("data-index")
                            print(f"\n处理第 {i}/{len(virtual_items)} 条帖子 (索引: {post_index})")
                            
                            # 获取帖子内容
                            post = virtual_item.query_selector("div[class*='post-content']")
                            if not post:
                                print(f"未找到帖子内容，跳过")
                                continue
                                
                            post_data = self.process_single_post(page, post, post_index)
                            if post_data:
                                posts.append(post_data)
                            
                            # 每处理5条保存一次完整数据
                            if i % 5 == 0:
                                self.save_data(posts, "cmc_btc_analysis.json")
                                print(f"已保存 {len(posts)} 条帖子的完整数据")
                        
                        # 如果已处理的帖子数量不足，继续滚动加载
                        while len(posts) < target_count:
                            print(f"\n当前已处理 {len(posts)} 条帖子，未达到目标数量 {target_count}，继续加载...")
                            
                            # 记录当前最后一个帖子的data-index
                            last_virtual_item = virtual_items[-1]
                            last_index = int(last_virtual_item.get_attribute("data-index"))
                            print(f"当前最后一个帖子的索引: {last_index}")
                            
                            # 滚动到底部
                            page.mouse.wheel(0, 500)
                            time.sleep(5)  # 等待新内容加载
                            
                            # 获取新加载的帖子
                            new_virtual_items = []
                            for i in range(1, 4):  # 尝试获取最多4个新帖子
                                next_index = last_index + i
                                new_item = page.query_selector(f"div[data-test='virtual-item'][data-index='{next_index}']")
                                if new_item:
                                    new_virtual_items.append(new_item)
                                else:
                                    break

                            # next_index = last_index + 1
                            # new_item = page.query_selector(f"div[data-test='virtual-item'][data-index='{next_index}']")
                            # if new_item:
                            #     new_virtual_items.append(new_item)
                            # if not new_virtual_items:
                            #     print("没有更多内容可加载")
                            #     break
                            
                            print(f"新加载了 {len(new_virtual_items)} 条帖子")
                            
                            # 处理新加载的帖子
                            for virtual_item in new_virtual_items:
                                # 获取帖子索引
                                post_index = virtual_item.get_attribute("data-index")
                                print(f"\n处理新加载的帖子 (索引: {post_index}, 当前总数: {len(posts) + 1})")
                                
                                # 获取帖子内容
                                post = virtual_item.query_selector("div[class*='post-content']")
                                if not post:
                                    print(f"未找到帖子内容，跳过")
                                    continue
                                    
                                post_data = self.process_single_post(page, post, post_index)
                                if post_data:
                                    posts.append(post_data)
                                
                                # 每处理5条保存一次完整数据
                                if len(posts) % 5 == 0:
                                    self.save_data(posts, "cmc_btc_analysis.json")
                                    print(f"已保存 {len(posts)} 条帖子的完整数据")
                                
                                # 如果达到目标数量，退出循环
                                if len(posts) >= target_count:
                                    break
                            
                            # 更新帖子列表
                            virtual_items.extend(new_virtual_items)
                            
                            # 如果已经获取到足够数量的帖子，退出循环
                            if len(posts) >= target_count:
                                break
                        
                        # 最终保存完整数据
                        self.save_data(posts, "cmc_btc_analysis.json")
                        print(f"成功爬取 {len(posts)} 条BTC分析帖子")
                        break  # 成功获取数据，退出重试循环
                        
                    except Exception as e:
                        print(f"爬取过程出错: {e}")
                        retry_count += 1
                        if retry_count < self.max_retries:
                            print(f"将在5秒后重试...")
                            time.sleep(5)
                    finally:
                        context.close()
                        browser.close()
            except Exception as e:
                print(f"Playwright初始化失败: {e}")
                retry_count += 1
                if retry_count < self.max_retries:
                    print(f"将在5秒后重试...")
                    time.sleep(5)
        
        return posts

    def crawl_price_data(self):
        """爬取价格数据"""
        try:
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(
                        headless=False,
                        args=['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
                    )
                except Exception as e:
                    print(f"启动Chromium失败，尝试使用Firefox: {e}")
                    browser = p.firefox.launch(
                        headless=False,
                        args=['--disable-gpu']
                    )
                
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
                )
                page = context.new_page()
                
                try:
                    print("正在获取BTC价格数据...")
                    page.goto("https://coinmarketcap.com/currencies/bitcoin/", wait_until='networkidle')
                    page.wait_for_selector("[data-price-target='price']", timeout=30000)
                    
                    # 获取当前价格
                    price_element = page.query_selector("[data-price-target='price']")
                    current_price = price_element.inner_text() if price_element else "Unknown"
                    
                    # 获取24h变化
                    change_element = page.query_selector("span[class*='change-percent']")
                    price_change = change_element.inner_text() if change_element else "Unknown"
                    
                    price_data = {
                        "current_price": current_price,
                        "price_change_24h": price_change,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    self.save_data([price_data], "btc_price_data.json")
                    print("价格数据爬取完成")
                    
                except Exception as e:
                    print(f"价格数据爬取失败: {e}")
                finally:
                    context.close()
                    browser.close()
        except Exception as e:
            print(f"Playwright初始化失败: {e}")

    def save_data(self, data, filename):
        """保存数据到文件"""
        filepath = os.path.join(self.data_path, filename)
        if isinstance(data, pd.DataFrame):
            data.to_csv(filepath, index=False, encoding='utf-8')
        elif isinstance(data, list):
            # 确保目录存在
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            # 保存为JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")

    def crawl_technical_indicators(self):
        """爬取技术指标数据"""
        # 这里可以添加从TradingView或其他来源爬取技术指标的逻辑
        pass

    def process_single_article(self, page, article):
        """处理单篇文章"""
        try:
            # 1. 获取文章基本信息
            title_element = article.query_selector("span[data-test='article-title']")
            title = title_element.inner_text().strip() if title_element else ""
            
            author_element = article.query_selector("span.author-name")
            author = author_element.inner_text().strip() if author_element else ""
            
            date_element = article.query_selector("span.article-date")
            date = date_element.inner_text().strip() if date_element else ""
            
            # 2. 获取文章链接
            article_link = article.query_selector("a[target='_blank']")
            if not article_link:
                print("未找到文章链接")
                return None
                
            article_url = article_link.get_attribute("href")
            if not article_url:
                print("未找到文章URL")
                return None
            
            # 3. 在新页面中获取文章内容
            new_page = page.context.new_page()
            try:
                new_page.goto(article_url, wait_until="domcontentloaded")
                time.sleep(5)  # 等待页面加载
                
                # 导出页面内容到文件
                new_page.wait_for_selector("article", timeout=10000)
                article_element = new_page.query_selector("article")
                
                if not article_element:
                    print("未找到文章内容")
                    return None
                
                # 获取文章标题
                detail_title = article_element.query_selector("h1")
                if detail_title:
                    detail_title = detail_title.inner_text().strip()
                
                # 获取文章内容
                content_elements = article_element.query_selector_all("div.base-text")
                if not content_elements:
                    print("未找到文章内容")
                    return None
                
                # 合并所有base-text的内容
                content_parts = []
                for content_element in content_elements:
                    text = content_element.inner_text().strip()
                    if text:
                        content_parts.append(text)
                
                content = "\n\n".join(content_parts)
                
                # 获取文章图片
                images = []
                image_elements = article_element.query_selector_all("img")
                for img in image_elements:
                    img_url = img.get_attribute("src")
                    if img_url:
                        images.append(img_url)
                
                # 获取文章标签
                tags = []
                tag_elements = article_element.query_selector_all("a.article-tag")
                for tag in tag_elements:
                    tag_text = tag.inner_text().strip()
                    if tag_text:
                        tags.append(tag_text)
                
                # 获取文章统计信息
                views_element = article_element.query_selector("span.article-views")
                views = views_element.inner_text().strip() if views_element else "0"
                
                comments_element = article_element.query_selector("span.article-comments")
                comments = comments_element.inner_text().strip() if comments_element else "0"
                
                # 整理数据
                article_data = {
                    "title": detail_title or title,  # 优先使用详情页的标题
                    "author": author,
                    "date": date,
                    "content": content,
                    "images": images,
                    "tags": tags,
                    "views": views,
                    "comments": comments,
                    "url": article_url,
                    "crawl_time": datetime.now().isoformat()
                }
                
                return article_data
                
            finally:
                new_page.close()
        except Exception as e:
            print(f"处理文章时出错: {e}")
            return None

    def crawl_articles(self):
        """爬取文章列表"""
        articles = []
        retry_count = 0
        target_count = 20  # 目标获取的文章数量
        
        while retry_count < self.max_retries:
            try:
                with sync_playwright() as p:
                    try:
                        browser = p.chromium.launch(
                            headless=False,
                            args=['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
                        )
                    except Exception as e:
                        print(f"启动Chromium失败，尝试使用Firefox: {e}")
                        browser = p.firefox.launch(
                            headless=False,
                            args=['--disable-gpu']
                        )
                    
                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
                    )
                    page = context.new_page()
                    
                    try:
                        print(f"正在访问CoinMarketCap文章列表... (尝试 {retry_count + 1}/{self.max_retries})")
                        
                        # 设置页面超时
                        page.set_default_timeout(self.timeout)
                        
                        # 访问页面
                        page.goto(self.articles_url, wait_until="domcontentloaded")
                        
                        # 等待页面加载
                        page.wait_for_load_state("networkidle", timeout=self.timeout)
                        time.sleep(5)  # 等待动态内容加载
                        
                        # 获取文章列表
                        article_elements = page.query_selector_all("div[data-test='article-item']")
                        if not article_elements:
                            raise Exception("未找到任何文章内容")
                        
                        print(f"初始加载了 {len(article_elements)} 篇文章")
                        
                        # 处理文章
                        for i, article in enumerate(article_elements, 1):
                            print(f"\n处理第 {i}/{len(article_elements)} 篇文章")
                            
                            article_data = self.process_single_article(page, article)
                            if article_data:
                                articles.append(article_data)
                            
                            # 每处理5条保存一次完整数据
                            if i % 5 == 0:
                                self.save_data(articles, "cmc_articles.json")
                                print(f"已保存 {len(articles)} 篇文章的完整数据")
                            
                            # 如果达到目标数量，退出循环
                            if len(articles) >= target_count:
                                break
                        
                        # 最终保存完整数据
                        self.save_data(articles, "cmc_articles.json")
                        print(f"成功爬取 {len(articles)} 篇文章")
                        break  # 成功获取数据，退出重试循环
                        
                    except Exception as e:
                        print(f"爬取过程出错: {e}")
                        retry_count += 1
                        if retry_count < self.max_retries:
                            print(f"将在5秒后重试...")
                            time.sleep(5)
                    finally:
                        context.close()
                        browser.close()
            except Exception as e:
                print(f"Playwright初始化失败: {e}")
                retry_count += 1
                if retry_count < self.max_retries:
                    print(f"将在5秒后重试...")
                    time.sleep(5)
        
        return articles

if __name__ == "__main__":
    # 设置控制台输出编码
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    crawler = FinancialDataCrawler()
    crawler.crawl_market_news()
    crawler.crawl_articles()  # 添加文章爬取
    # crawler.crawl_price_data() 