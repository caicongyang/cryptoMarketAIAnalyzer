import os
import time
from datetime import datetime
from dotenv import load_dotenv
from src.services.analyzer import MarketAnalyzer
from src.services.crawler import FinancialDataCrawler
from services.BinancePublisher import BinancePublisher

class CryptoMarketBot:
    def __init__(self):
        """初始化加密货币市场机器人"""
        # 加载环境变量
        load_dotenv()
        
        # 初始化组件
        self.crawler = FinancialDataCrawler()
        self.analyzer = MarketAnalyzer()
        self.publisher = BinancePublisher()
        
        # 设置数据目录
        self.data_dir = os.getenv('DATA_SAVE_PATH', './data')
        os.makedirs(self.data_dir, exist_ok=True)

    def run_data_collection(self):
        """运行数据收集流程"""
        try:
            print("\n=== 开始数据收集 ===")
            print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1. 爬取市场新闻
            print("\n1. 爬取市场分析帖子...")
            self.crawler.crawl_market_news()
            
            # 2. 爬取文章
            print("\n2. 爬取市场分析文章...")
            self.crawler.crawl_articles()
            
            # 3. 爬取价格数据
            print("\n3. 爬取BTC价格数据...")
            self.crawler.crawl_price_data()
            
            print("\n数据收集完成！")
            return True
            
        except Exception as e:
            print(f"\n数据收集过程出错: {str(e)}")
            return False

    def run_analysis(self):
        """运行数据分析流程"""
        try:
            print("\n=== 开始数据分析 ===")
            print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 运行市场分析
            self.analyzer.run_analysis()
            
            # 生成投资建议
            print("\n生成投资建议...")
            result = self.analyzer.generate_investment_recommendation()
            
            if result["status"] == "success":
                print("投资建议生成成功！")
                return True
            else:
                print(f"投资建议生成失败: {result['message']}")
                return False
                
        except Exception as e:
            print(f"\n数据分析过程出错: {str(e)}")
            return False

    def publish_to_binance(self):
        """发布分析结果到币安"""
        try:
            print("\n=== 开始发布到币安 ===")
            print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 使用Publisher推送投资建议到币安
            result = self.publisher.push_recommendation()
            
            if result["status"] == "success":
                print("成功发布到币安社区！")
                return True
            else:
                print(f"发布失败: {result['message']}")
                if "screenshot" in result:
                    print(f"错误截图已保存: {result['screenshot']}")
                return False
                
        except Exception as e:
            print(f"\n发布过程出错: {str(e)}")
            return False

    def run(self, interval_minutes=60):
        """运行完整的工作流程"""
        print("\n=== 加密货币市场分析机器人启动 ===")
        print(f"数据目录: {self.data_dir}")
        print(f"运行间隔: {interval_minutes}分钟")
        
        while True:
            try:
                # 1. 收集数据
                if not self.run_data_collection():
                    print("数据收集失败，等待下一次运行...")
                    time.sleep(300)  # 5分钟后重试
                    continue
                
                # 2. 分析数据
                if not self.run_analysis():
                    print("数据分析失败，等待下一次运行...")
                    time.sleep(300)
                    continue
                
                # 3. 发布到币安
                if not self.publish_to_binance():
                    print("发布失败，等待下一次运行...")
                    time.sleep(300)
                    continue
                
                print(f"\n工作流程完成，等待{interval_minutes}分钟后进行下一次运行...")
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                print("\n程序被用户中断")
                break
            except Exception as e:
                print(f"\n运行过程出错: {str(e)}")
                print("5分钟后重试...")
                time.sleep(300)

def main():
    """主函数"""
    bot = CryptoMarketBot()
    # 设置运行间隔为60分钟
    bot.run(interval_minutes=60)

if __name__ == "__main__":
    main() 