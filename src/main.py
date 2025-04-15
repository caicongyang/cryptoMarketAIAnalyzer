import schedule
import time
from services.crawler import FinancialDataCrawler
from services.analyzer import MarketAnalyzer
from services.BinancePublisher import BinancePublisher
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class CryptoAnalysisBot:
    def __init__(self):
        self.crawler = FinancialDataCrawler()
        self.analyzer = MarketAnalyzer()
        self.publisher = BinancePublisher()
        self.interval = int(os.getenv('CRAWLER_INTERVAL', 3600))

    def run_analysis(self):
        """执行完整的分析和发布流程"""
        try:
            print(f"开始分析任务 - {datetime.now()}")
            
            # 1. 收集数据
            self.crawler.crawl_market_news()
            self.crawler.crawl_articles() 
            
            # 2. AI分析
            self.analyzer.analyze_articles()
            self.analyzer.analyze_posts()
           
            
            # 3. 生成报告
            self.analyzer.generate_investment_recommendation()
        
            # 4. 发布到Binance Square
            self.publisher.push_recommendation()
            
            print(f"分析任务完成 - {datetime.now()}")
            
        except Exception as e:
            print(f"运行错误: {e}")

def main():
    bot = CryptoAnalysisBot()
    
    # 设置定时任务
    schedule.every(bot.interval).seconds.do(bot.run_analysis)
    
    # 先运行一次
    bot.run_analysis()
    
    # 持续运行定时任务
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main() 