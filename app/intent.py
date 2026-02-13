"""
最簡版意圖分類器
規則判定為主，OpenAI 兜底
"""
import os
import re
from typing import Dict, Any, Optional
import openai

class IntentClassifier:
    """
    意圖分類器
    輸出：yes / no / CHOICE_KEY / unknown
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.use_openai = bool(self.api_key)
    
    def classify(
        self, 
        user_input: str, 
        node: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        判定用戶意圖
        
        Returns:
            "yes" | "no" | choice_key | "unknown"
        """
        text = user_input.strip().lower()
        
        # 1. 規則判定（最優先）
        rule_result = self._rule_classify(text)
        if rule_result:
            return rule_result
        
        # 2. 選項模糊匹配
        if node and node.get("choices"):
            choice_match = self._match_choice(text, node["choices"])
            if choice_match:
                return choice_match
        
        # 3. OpenAI 兜底
        if self.use_openai:
            return self._openai_classify(text, node)
        
        return "unknown"
    
    def _rule_classify(self, text: str) -> Optional[str]:
        """規則判定"""
        # 是/Yes
        if re.search(r"^(是|对|好|行|可以|沒問題|yes|yep|yeah|ok|sure|要|想)$", text):
            return "yes"
        
        # 否/No
        if re.search(r"^(否|不|不用|不要|不行|沒有|no|nope|nah|否.*)$", text):
            return "no"
        
        # 數字選擇
        if re.match(r"^(\d+)$", text):
            return text  # 回傳數字作為 choice key
        
        return None
    
    def _match_choice(self, text: str, choices: list) -> Optional[str]:
        """模糊匹配選項"""
        for choice in choices:
            key = choice.get("key", "").lower()
            label = choice.get("label", "").lower()
            
            # 精確匹配
            if text == key or text == label:
                return key
            
            # 包含匹配
            if text in label or label in text:
                return key
        
        return None
    
    def _openai_classify(
        self, 
        text: str, 
        node: Optional[Dict[str, Any]]
    ) -> str:
        """OpenAI 兜底判定"""
        try:
            choices_info = ""
            if node and node.get("choices"):
                choices_text = ", ".join([c["key"] for c in node["choices"]])
                choices_info = f"可選項目: {choices_text}"
            
            prompt = f"""判定用戶意圖，只回傳以下其中一種：
- "yes"（同意/確認/是）
- "no"（拒絕/否定/否）
- 選項名稱（如果用戶選擇了特定項目）
- "unknown"（無法判定）

{choices_info}
用戶輸入: "{text}"

只回傳結果，不要解釋："""
            
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是意圖分類助手，只回傳單一詞。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0
            )
            
            result = response.choices[0].message.content.strip().lower()
            
            # 驗證回傳值
            valid = ["yes", "no", "unknown"]
            if result in valid:
                return result
            
            # 檢查是否為選項
            if node and node.get("choices"):
                for choice in node["choices"]:
                    if result == choice["key"].lower():
                        return choice["key"]
            
            return "unknown"
            
        except Exception as e:
            print(f"OpenAI error: {e}")
            return "unknown"
