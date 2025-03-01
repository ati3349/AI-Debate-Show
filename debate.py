import os
import time
import json
from openai import OpenAI
import httpx
import random


# ================== 基础模块 ==================
class Debater:
    def __init__(self, config, proxies):
        self.config = config 
        self.model_name = config["name"]
        # 创建 OpenAI 客户端，配置代理
        if config["agent"]:
            print("%s需要代理"%config["name"])
            # 代理设置
            proxies = proxies
            
            # 创建同步客户端
            self.client = OpenAI(
                api_key=config["api_key"],  
                base_url=config["base_url"],http_client=httpx.Client(proxies=proxies)  # 使用 httpx 设置代理
            )
        else:
            self.client = OpenAI(api_key=config["api_key"],base_url=config["base_url"])  


    def generate_response(self, prompt):
        """向Ai提问"""
        try:
            response = self.client.chat.completions.create(
                model= self.config["model"], 
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"[API错误] {str(e)}"

# ================== 评委模块 ==================
class DebateJudge(Debater):
    def __init__(self, config, proxies):
        super().__init__(config, proxies)
    
    def generate_topic(self):
        """生成辩论题目"""
        prompt = """请生成一个适合AI辩论的争议性辩题，要求：
        1. 涉及科技伦理或社会热点 
        2. 正反双方都有充足论据
        3. 使用「XXX应该XXX/不应该XXX」格式
        4. 已经用过的不要再使用，包括：['人类应该全面禁止基因编辑技术/不应该全面禁止','人类应该让机器人承担所有危险工作/不应该让机器人承担所有危险工作',]
        输出示例：{"topic": "人类应该允许AI拥有自主军事决策权/不应该允许"}"""
        result = self.generate_response(prompt)
        try:
            return json.loads(result)["topic"]
        except:
            return "AI生成内容应强制标注来源/无需标注来源"  # 默认辩题

    def evaluate_performance(self, debate_history):
        """生成比赛点评"""
        history_text = json.dumps(debate_history, ensure_ascii=False)[:3000]
        prompt = f"""作为专业辩论赛评委，请根据以下比赛记录：
        {history_text}
        
        从以下维度进行点评：
        1. 论点创新性（举例说明最亮眼的论点）
        2. 攻防表现（质询环节有效性分析）
        要求：
        - 包含正反双方各一个「最佳瞬间」片段
        - 最后给出象征性比分（如5:4）"""
        return self.generate_response(prompt)


# ================== 升级版辩论引擎 ==================
class EnhancedDebateEngine:
    def __init__(self,judge, models,proxies, max_depth=2):
        
        self.debaters = [Debater(model,proxies) for model in models]
        self.history = []
        self.max_depth = max_depth  # 最大追问层数
        # 初始化AI评委
        self.judge = DebateJudge(judge,proxies) 
        
    
    def run_round(self, round_type, **kwargs):
        round_data = {"type": round_type, "speeches": []}
        """辩论环节控制器"""

        # 立论阶段
        if round_type == "constructive":
            for i, debater in enumerate(self.debaters):
                prompt = f"""作为{'正方' if i==0 else '反方'}辩手，请就辩题《{self.topic}》发表2分钟立论陈词，要求：
                1. 提出核心论点 
                2. 论点附带事例支撑 
                3. 使用排比修辞"""
                speech = self.debaters[i].generate_response(prompt)
                round_data["speeches"].append({
                    "model": debater.model_name,
                    "content": speech
                })
        
        # 质询阶段
        elif round_type == "rebuttal":
            for i, debater in enumerate(self.debaters):
                opponent_speech = self.history[-1]["speeches"][(i+1)%2]["content"]
                prompt = f"""你现在的身份是{'反方' if i==0 else '正方'}辩手，请针对以下对方立论进行反驳：
                对方论点：{opponent_speech[:500]}...
                要求：
                1. 指出2个逻辑漏洞
                2. 提出1个反例
                3. 结尾使用反问句加强气势"""
                #messages={"role": "user", "content": prompt}
                speech = self.debaters[i].generate_response(prompt)
                round_data["speeches"].append({
                    "model": self.debaters[i].model_name,
                    "content": speech["content"]
                })
        #连环追问
        elif round_type == "dynamic_rebuttal":
            return self.dynamic_rebuttal(kwargs.get('init_prompt'), 
                                       kwargs.get('depth', 0))  
        
        elif round_type == "closing":
            return self.closing_statements()
        #开场白
        elif round_type == "prologue":
            round_data = {"type": round_type, "speeches": []}
            prompt = '''欢迎来到AI辩论赛！
                今天，我们不再讨论AI能做什么，而是聚焦于它们如何思考。
                让我们看看，代码如何演绎逻辑，算法怎样诠释语言。
                我们邀请到两位大语言模型，请用一句话介绍一下自己。'''
            round_data["speeches"].append({
                    "model": "主持人",
                    "content": prompt
                })
            
            for i, debater in enumerate(self.debaters):
                speech = self.debaters[i].generate_response(prompt)
                round_data["speeches"].append({
                    "model": debater.model_name,
                    "content": speech
                }) 
                
            prompt = '''我们还邀请了一位AI，作为今天的评委，为我们出辩题和进行点评，请评委老师介绍一下自己'''
            round_data["speeches"].append({
                    "model": "主持人",
                    "content": prompt
                })
            prompt = '''你现在的身份是辩论会评委，你叫什么？请用一句话介绍一下自己'''
                
            speech = self.judge.generate_response(prompt)  
            round_data["speeches"].append({
                "model": self.judge.model_name,
                "content": speech
            })                 
            # 生成辩题
            self.topic = self.judge.generate_topic()    
            round_data["speeches"].append({
                "model": self.judge.model_name,
                "content": "今天的辩题是《%s》"%self.topic
            })  
            
            # 抽签...使用random.shuffle()来打乱列表的顺序
            random.shuffle(self.debaters)
            
            prompt = '''谢谢%s，下面抽签... 正反是%s,反方是%s。请正方发言'''%(self.judge.model_name,
                                                           self.debaters[0].model_name,self.debaters[1].model_name)
            round_data["speeches"].append({
                    "model": "主持人",
                    "content": prompt
                })            
            
        #加入记录
        self.history.append(round_data)
        return round_data
        

    
    def closing_statements(self):
        """总结陈词环节"""
        round_data = {"type": "closing", "speeches": []}
        for i, debater in enumerate(self.debaters):
            prompt = f"""作为{'正方' if i==0 else '反方'}最终陈述者，请：
            一句话总结
            当前辩题：{self.topic}
            历史交锋摘要：{self.get_summary()}"""
            speech = debater.generate_response(prompt)
            round_data["speeches"].append({
                "model": debater.model_name,
                "content": speech
            })
        self.history.append(round_data)
        return round_data
    
    def dynamic_rebuttal(self, init_prompt, depth=0):
        """执行实时连环追问"""
        if depth >= self.max_depth:
            return None

        round_data = {
            "type": f"dynamic_rebuttal_{depth+1}",
            "speeches": [],
            "depth": depth+1
        }

        # 交替获取双方辩手的追问
        for i in range(len(self.debaters)):
            # 获取前一次发言作为反驳目标
            prev_speech = self.get_last_speech(opponent=(i+1)%2)
            
            # 动态生成追问提示词
            prompt = f"""作为{'正方' if i==0 else '反方'}辩手，请进行第{depth+1}轮追问：
            {init_prompt}
            需要针对以下最新发言进行反驳：
            <<对方发言>>{prev_speech[:500]}...
            要求：
            1. 指出1个新漏洞 
            2. 使用类比论证
            3. 结尾用挑战性问句"""
            
            speech = self.debaters[i].generate_response(prompt)
            round_data["speeches"].append({
                "model": self.debaters[i].model_name,
                "content": speech
            })

        self.history.append(round_data)
        # 递归实现连续追问
        self.dynamic_rebuttal(init_prompt, depth+1)
        return round_data    
    
    def get_last_speech(self, opponent=False):
        """获取指定辩手的最近发言"""
        target_index = 1 if opponent else 0
        for record in reversed(self.history):
            if "speeches" in record:
                return record["speeches"][target_index]["content"]
        return ""    
    
    def get_summary(self):
        """生成辩论摘要"""
        return "\n".join([f"Round {i}: {r['type']}" 
                        for i, r in enumerate(self.history)])

    def start_debate(self):
        """主流程"""
        # 开场白
        self.run_round("prologue")
        print("=== 开场白 ===")
        self.print_round(-1)        
        
        
        # 生成辩题
        #self.topic = self.judge.generate_topic()
        
        print(f"【辩论开始】辩题：{self.topic}\n")
        
        # 标准环节
        self.run_round("constructive")
        print("=== 立论陈词 ===")
        self.print_round(-1)

        
        self.run_round("dynamic_rebuttal", 
                      init_prompt="请展开多轮深入追问：")
        print("\n=== 实时追问 ===")
        self.print_dynamic_rounds()

        # 总结陈词
        self.run_round("closing")
        print("\n=== 总结陈词 ===")
        self.print_round(-1)
        
        # 生成点评
        print("\n=== AI评委点评 ===")
        round_data = {"type": "评委点评", "speeches": []}
        round_data["speeches"].append({
                "model": "主持人",
                "content": "谢谢两位辩手的精彩表现。请评委点评"
            })            
            
        #加入记录
        self.history.append(round_data)    
        self.print_round(-1)
        
        result = self.export_result()
        evaluation = self.judge.evaluate_performance(result["history"])
        #print(evaluation)   
        round_data = {"type": "评委点评", "speeches": []}
        round_data["speeches"].append({
                "model": self.judge.model_name,
                "content": evaluation
            })            
            
        #加入记录
        self.history.append(round_data)  
        self.print_round(-1)
        

        return self.history
    
    def print_dynamic_rounds(self):
        """专用打印方法"""
        for round in self.history:
            if "dynamic_rebuttal" in round["type"]:
                print(f"== 第{round['depth']}层追问 ==")
                self.print_round(self.history.index(round))
    
    
    def print_round(self, index):
        """打印指定回合内容"""
        #print("打印指定回合内容")
        for speech in self.history[index]["speeches"]:
            print(f"[{speech['model']}]\n{speech['content']}\n{'-'*40}")    
    
    
    def export_result(self):
        """导出结构化记录"""
        return {
            "topic": self.topic,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "history": self.history
        }    

# ================== 主程序 ==================
if __name__ == "__main__":
    ailist = [
         {"api_key":"sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",# 替换为你的 OpenAI API 密钥
          "base_url":"https://api.hunyuan.cloud.tencent.com/v1",
          "model":"hunyuan-turbo",
          "name":"混元",
          "agent":0                  
         },
        {"api_key":"sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",# 替换为你的 OpenAI API 密钥
          "base_url":"https://ark.cn-beijing.volces.com/api/v3",
          "model":"ep-20250212173603-h49nw",#"Doubao-1.5-pro-256k",#
          "name":"豆包",
          "agent":0                 
         },
        {"api_key":"sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",# 替换为你的 OpenAI API 密钥
          "base_url":"https://api.x.ai/v1",
          "model":"grok-2-latest",
          "name":"Grok",
          "agent":1               
         }
        
    ]
    #代理服务器（如果需要）
    proxies = {
            "http://": "xxxxxxxxxxxxx",#替换为你的代理
            "https://": "xxxxxxxxxxxxxxxxxx",#替换为你的代理
        }
    
    # 运行辩论
    debate = EnhancedDebateEngine(
        judge=ailist[1],
        models=[ailist[0],ailist[2]],
        proxies=proxies,
        max_depth=2
    )
    
    result = debate.start_debate()
    # 保存完整记录
    with open("enhanced_debate_log.json", "w", encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        
        print('ok!')