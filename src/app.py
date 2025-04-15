from flask import Flask, render_template, jsonify, request
import os
from services.crawler import FinancialDataCrawler
from services.analyzer import MarketAnalyzer
from services.BinancePublisher import BinancePublisher
from services.WXPublisher import WXPublisher
from datetime import datetime
import json
import subprocess
import time
import asyncio

# 启动调试模式的Chrome
# chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# debugging_port = "9222"
# command = f'"{chrome_path}" --remote-debugging-port={debugging_port}'
# subprocess.Popen(command, shell=True)
# time.sleep(2)  # 等待Chrome启动

app = Flask(__name__)
analyzer = MarketAnalyzer()
binance_publisher = BinancePublisher()
wx_publisher = WXPublisher()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/crawl', methods=['POST'])
def crawl():
    try:
        crawler = FinancialDataCrawler()
        crawler.crawl_market_news()
        crawler.crawl_articles()
        return jsonify({"status": "success", "message": "爬取完成"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        analyzer.run_analysis()
        return jsonify({"status": "success", "message": "分析完成"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/results', methods=['GET'])
def get_results():
    try:
        # 读取分析结果
        article_analysis = analyzer._load_json("article_analysis.json")
        post_analysis = analyzer._load_json("post_analysis.json")
        recommendation_analysis = analyzer._load_json("investment_recommendation.json")
        
        return jsonify({
            "status": "success",
            "data": {
                "article_analysis": article_analysis,
                "post_analysis": post_analysis,
                "recommendation_analysis": recommendation_analysis
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/update_analysis', methods=['POST'])
def update_analysis():
    try:
        data = request.json
        if 'article_analysis' in data:
            analyzer._save_json(data['article_analysis'], "article_analysis.json")
        
        if 'post_analysis' in data:
            analyzer._save_json(data['post_analysis'], "post_analysis.json")
        
        return jsonify({"status": "success", "message": "更新成功"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/generate_recommendation', methods=['POST'])
def generate_recommendation():
    try:
        result = analyzer.generate_investment_recommendation()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/push_to_binance', methods=['POST'])
def push_to_binance():
    try:
        result = binance_publisher.push_recommendation()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/push_to_weixin', methods=['POST'])
def push_to_weixin():
    try:
        # 创建事件循环来运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(wx_publisher.push_recommendation())
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

if __name__ == '__main__':
    app.run(debug=True) 