import os
import json
import openai
import logging
from datetime import datetime
import requests
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("market-analyzer")

# 配置OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
openai.api_base = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
openai.api_model = os.getenv('MODEL', 'gpt-4o')
openai.api_temperature = float(os.getenv('PREDICTION_THRESHOLD', '0.75').split('#')[0].strip())

class MarketAnalyzer:
    def __init__(self):
        # 先加载环境变量
        load_dotenv()

        # 设置数据路径和API配置
        self.data_path = os.getenv('DATA_SAVE_PATH', './data')
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.api_base = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
        self.api_model = os.getenv('MODEL', 'gpt-4o')
        self.api_temperature = float(os.getenv('PREDICTION_THRESHOLD', '0.75').split('#')[0].strip())  # 转换为浮点数

        logger.info(f"API Base URL: {self.api_base}")  # 调试信息

        self.data_dir = 'data'
        os.makedirs(self.data_dir, exist_ok=True)

    def _load_json(self, filename):
        """加载JSON文件"""
        filepath = os.path.join(self.data_path, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save_json(self, data, filename):
        """保存JSON文件"""
        filepath = os.path.join(self.data_path, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _call_ai_api(self, prompt):
        """调用AI API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": self.api_model,
            "messages": [
                {"role": "system", "content": "你是一个专业的加密货币市场分析师，擅长分析市场情绪和预测价格走势。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": float(self.api_temperature)
        }

        logger.debug("API请求参数：%s", json.dumps(data, ensure_ascii=False, indent=2))  # 调试信息

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            logger.error("HTTP错误: %s", e)
            logger.error("响应内容: %s", e.response.text)  # 打印详细错误信息
            return None
        except Exception as e:
            logger.error("调用AI API出错: %s", e)
            return None

    def analyze_articles(self):
        """分析文章"""
        articles = self._load_json("cmc_articles.json")
        if not articles:
            logger.warning("没有找到文章数据")
            return

        # 准备分析提示
        prompt = f"""
        请分析以下加密货币市场文章，并给出市场预测。请使用Markdown格式输出分析结果，包含以下部分：

        # 市场文章分析报告
        
        ## 1. 市场情绪分析
        - 总体情绪：（看涨/看跌/中性）
        - 情绪指数：（1-10）
        - 具体表现：
          * 观点1
          * 观点2
          * 观点3

        ## 2. 主要关注点
        1. 关注点1
           - 详细说明
           - 影响分析
        2. 关注点2
           - 详细说明
           - 影响分析

        ## 3. 市场趋势预测
        ### 短期预测（24小时内）
        - 价格区间：
        - 关键支撑位：
        - 关键阻力位：
        
        ### 中期预测（7天内）
        - 价格趋势：
        - 可能的突破点：
        - 风险因素：

        ## 4. 投资建议
        ### 建议操作
        - [ ] 建议1
        - [ ] 建议2
        - [ ] 建议3

        ### 风险提示
        > 重要风险提示和注意事项

        ## 5. 数据来源
        - 分析文章数量：{len(articles)}
        - 分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

        文章列表：
        {json.dumps(articles, ensure_ascii=False, indent=2)}
        """

        # 调用AI分析
        analysis = self._call_ai_api(prompt)
        if analysis:
            # 保存分析结果
            result = {
                "timestamp": datetime.now().isoformat(),
                "analysis": analysis,
                "type": "markdown"
            }
            self._save_json(result, "article_analysis.json")
            logger.info("文章分析完成")

    def analyze_posts(self):
        """分析帖子"""
        posts = self._load_json("cmc_btc_analysis.json")
        if not posts:
            logger.warning("没有找到帖子数据")
            return

        # 准备分析提示
        prompt = f"""
        请分析以下加密货币社区讨论，并给出市场预测。请使用Markdown格式输出分析结果，包含以下部分：

        # 社区讨论分析报告

        ## 1. 社区情绪分析
        - 总体情绪：（看涨/看跌/中性）
        - 情绪指数：（1-10）
        - 热点词汇：
          * 词汇1（出现频次）
          * 词汇2（出现频次）
          * 词汇3（出现频次）

        ## 2. 热门话题分析
        ### 主要话题
        1. 话题1
           - 讨论热度：
           - 社区观点：
           - 影响分析：
        2. 话题2
           - 讨论热度：
           - 社区观点：
           - 影响分析：

        ## 3. 市场趋势预测
        ### 社区共识
        - 短期预期：
        - 中期预期：
        - 争议焦点：

        ### 技术分析观点
        - 支撑位：
        - 阻力位：
        - 关键指标：

        ## 4. 投资建议
        ### 操作建议
        - [ ] 建议1
        - [ ] 建议2
        - [ ] 建议3

        ### 风险提示
        > 重要风险提示和注意事项

        ## 5. 数据来源
        - 分析帖子数量：{len(posts)}
        - 分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

        帖子列表：
        {json.dumps(posts, ensure_ascii=False, indent=2)}
        """

        # 调用AI分析
        analysis = self._call_ai_api(prompt)
        if analysis:
            # 保存分析结果
            result = {
                "timestamp": datetime.now().isoformat(),
                "analysis": analysis,
                "type": "markdown"
            }
            self._save_json(result, "post_analysis.json")
            logger.info("帖子分析完成")

    def run_analysis(self):
        """运行完整分析"""
        logger.info("开始分析文章...")
        self.analyze_articles()

        logger.info("开始分析帖子...")
        self.analyze_posts()

        logger.info("分析完成！")

    def generate_investment_recommendation(self):
        """生成投资建议"""
        try:
            # 从本地文件读取分析数据
            article_analysis_path = os.path.join(self.data_path, "article_analysis.json")
            post_analysis_path = os.path.join(self.data_path, "post_analysis.json")

            # 读取文章分析数据
            try:
                with open(article_analysis_path, 'r', encoding='utf-8') as f:
                    article_data = json.load(f)
                    article_analysis = article_data.get('analysis', '')
            except FileNotFoundError:
                logger.warning("未找到文章分析数据文件")
                article_analysis = ''
            except json.JSONDecodeError:
                logger.error("文章分析数据文件格式错误")
                article_analysis = ''

            # 读取社区讨论分析数据
            try:
                with open(post_analysis_path, 'r', encoding='utf-8') as f:
                    post_data = json.load(f)
                    post_analysis = post_data.get('analysis', '')
            except FileNotFoundError:
                logger.warning("未找到社区讨论分析数据文件")
                post_analysis = ''
            except json.JSONDecodeError:
                logger.error("社区讨论分析数据文件格式错误")
                post_analysis = ''

            # 如果两个数据源都为空，返回错误
            if not article_analysis and not post_analysis:
                return {
                    "status": "error",
                    "message": "无法获取分析数据，请先运行市场分析"
                }

            # 构建提示词
            prompt = f"""
作为一个币安博主，请基于以下市场分析数据，生成一份社区交流的帖子。

文章分析数据：
{article_analysis}

社区讨论分析：
{post_analysis}

请生成一份社区交流的帖子，包含以下部分：
1. 分享您的想法

在您的帖子中使用像$BTC 、$ETH 或$BNB 这样的币种标签，以便更清晰和更好的可见性。例如：

"比特币（$BTC）在突破关键阻力位后显示出看涨信号。"

2. 利用热门话题

关注热点话题，如主要价格波动、即将到来的区块链升级或监管新闻。例如：

"以太坊（$ETH）即将进行下次升级——这对投资者意味着什么。

要求：
1. 使用专业的投资术语
2. 提供具体的价格目标和支撑/阻力位
3. 给出明确的仓位配比建议
4. 包含风险管理策略
5. 语气要专业但友好，符合人类投资者的表述方式
6. 输出格式为Markdown
7. 输出字数不要太多，要符合社区发帖字数要求

请以```markdown开始，以```结束。
"""
            # 调用AI API生成建议
            recommendation = self._call_ai_api(prompt)

            if not recommendation:
                return {
                    "status": "error",
                    "message": "生成投资建议失败"
                }

            # 保存生成的建议到文件
            result = {
                "timestamp": datetime.now().isoformat(),
                "recommendation": recommendation,
                "type": "markdown"
            }
            self._save_json(result, "investment_recommendation.json")

            return {
                "status": "success",
                "recommendation": recommendation
            }

        except Exception as e:
            logger.error("生成投资建议时发生错误: %s", str(e))
            return {
                "status": "error",
                "message": f"生成投资建议失败: {str(e)}"
            }

if __name__ == "__main__":
    analyzer = MarketAnalyzer()
    analyzer.run_analysis()
