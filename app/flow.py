"""
Flow Engine - 支援醫療問診流程
欄位對應：
- 序號 → node_id
- 判斷問題 → prompt（問句）
- 症狀代碼 → tags.code
- 建議行動方向 → tags.action_tag
- 內容說明（衛教） → education_text
- 使用者回答肯定/否定/選項 → transitions
"""
import csv
import re
import pandas as pd
from typing import Dict, List, Optional, Any

class FlowEngine:
    """醫療問診流程引擎"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.is_loaded = False
        self._start_node: Optional[str] = None
    
    def load(self):
        """載入流程定義（支援 CSV 或 Excel）"""
        if self.file_path.endswith('.csv'):
            self._load_csv()
        else:
            self._load_excel()
        self.is_loaded = True
    
    def _load_csv(self):
        """從 CSV 載入"""
        with open(self.file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._parse_node(row)
    
    def _load_excel(self):
        """從 Excel 載入"""
        df = pd.read_excel(self.file_path)
        for _, row in df.iterrows():
            self._parse_node(row.to_dict())
    
    def _parse_node(self, row: dict):
        """解析單一節點"""
        # 支援多種可能的欄位名稱
        node_id = self._get_value(row, ["序號", "node_id", "id", "編號"])
        if not node_id:
            return
        
        node_id = str(node_id).strip()
        
        # 判斷是否有選項（是/否題 vs 多選題）
        yes_branch = self._get_value(row, ["使用者回答肯定…→ 進入分支", "肯定分支", "yes_branch", "transitions_yes"])
        no_branch = self._get_value(row, ["使用者回答否定…→ 進入分支", "否定分支", "no_branch", "transitions_no"])
        choices_str = self._get_value(row, ["選項", "choices", "選項分支"])
        education_text = self._get_value(row, ["內容說明（衛教）", "衛教", "education_text", "說明"], default="")
        
        # 如果沒有選項但 column 6 包含 | 且 yes/no 為空，則視為多選題
        if not choices_str and yes_branch == "" and no_branch == "":
            if education_text and "|" in education_text:
                choices_str = education_text
                education_text = ""
        
        # 建立 transitions
        transitions = {}
        if yes_branch and str(yes_branch).lower() not in ["nan", "", "none"]:
            transitions["yes"] = str(yes_branch).strip()
        if no_branch and str(no_branch).lower() not in ["nan", "", "none"]:
            transitions["no"] = str(no_branch).strip()
        
        # 解析多選項分支
        if choices_str and str(choices_str).lower() not in ["nan", "", "none"]:
            # 格式: "選項A|node_id,選項B|node_id" 或 "是|Q2,否|END"
            choices = self._parse_choices_with_transitions(str(choices_str))
            for choice in choices:
                if "next" in choice:
                    transitions[choice["key"]] = choice["next"]
        
        node = {
            "id": node_id,
            "prompt": self._get_value(row, ["判斷問題", "prompt", "question", "內容"], default=""),
            "education_text": education_text,
            "tags": {
                "code": self._get_value(row, ["症狀代碼", "code", "tags_code", "症狀"], default=""),
                "action_tag": self._get_value(row, ["建議行動方向", "action_tag", "action", "行動方向"], default="")
            },
            "transitions": transitions,
            "is_end": len(transitions) == 0  # 沒有分支就是結束節點
        }
        
        self.nodes[node_id] = node
        
        # 第一個節點設為起始節點
        if self._start_node is None:
            self._start_node = node_id
    
    def _get_value(self, row: dict, possible_keys: List[str], default: str = "") -> str:
        """從多個可能的欄位名稱中取得值"""
        for key in possible_keys:
            if key in row and row[key] is not None:
                value = str(row[key]).strip()
                if value and value.lower() not in ["nan", "none", "null"]:
                    return value
        return default
    
    def _parse_choices_with_transitions(self, choices_str: str) -> List[Dict[str, str]]:
        """解析選項與對應的下一節點"""
        choices = []
        # 支援多種分隔符號
        for item in choices_str.replace("；", ";").replace("\n", ";").replace(",", ";").split(";"):
            item = item.strip()
            if not item:
                continue
            
            # 格式: "選項文字|下一節點ID" 或 "選項文字"
            if "|" in item:
                parts = item.split("|", 1)
                label = parts[0].strip()
                next_node = parts[1].strip() if len(parts) > 1 else ""
                key = label.lower().replace(" ", "_")
                choice = {"label": label, "key": key}
                if next_node:
                    choice["next"] = next_node
                choices.append(choice)
            else:
                choices.append({"label": item, "key": item.lower().replace(" ", "_")})
        
        return choices
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """取得節點"""
        return self.nodes.get(node_id)
    
    def get_start_node(self) -> str:
        """取得起始節點"""
        return self._start_node or "1"
    
    def get_next_node(
        self, 
        current: Optional[Dict[str, Any]], 
        intent: str, 
        user_input: str
    ) -> Optional[str]:
        """
        決定下一個節點
        
        Args:
            current: 當前節點
            intent: 意圖（yes/no/choice_key/unknown）
            user_input: 用戶原始輸入
        
        Returns:
            下一節點 ID，若無則回傳 None（結束）
        """
        if not current:
            return None
        
        transitions = current.get("transitions", {})
        
        # 1. 優先用意圖匹配（yes/no）
        if intent in transitions:
            return transitions[intent]
        
        # 1.5. 如果 intent 是 unknown，嘗試用戶輸入中是否有 是/否
        if intent == "unknown":
            user_lower = user_input.strip().lower()
            if re.search(r'(是|對|好|可以|yes|yep|yeah|ok|要|想)', user_lower):
                if "yes" in transitions:
                    return transitions["yes"]
            if re.search(r'(否|不|不要|不行|沒有|no|nope|nah)', user_lower):
                if "no" in transitions:
                    return transitions["no"]

        # 1.7. 數字選項（1/2/3）依 transitions 順序對應
        if intent.isdigit():
            index = int(intent) - 1
            transition_items = list(transitions.items())
            if 0 <= index < len(transition_items):
                return transition_items[index][1]
        
        # 2. 嘗試匹配選項 key（針對多選題）
        user_input_lower = user_input.strip().lower()
        user_input_normalized = user_input_lower.replace(" ", "_")
        for key, next_node in transitions.items():
            key_lower = key.lower()
            key_normalized = key_lower.replace(" ", "_")
            if user_input_lower == key_lower or user_input_normalized == key_normalized:
                return next_node
        
        # 3. 模糊匹配選項文字
        for key, next_node in transitions.items():
            key_normalized = key.lower().replace(" ", "_")
            if (
                key_normalized in user_input_normalized
                or user_input_normalized in key_normalized
            ):
                return next_node

        # 3.5. 關鍵字匹配（針對第10題治療選項）
        keyword_groups = [
            ("hormone", ["雌激素", "賀爾蒙", "hormonal", "estrogen"]),
            ("ha", ["ha", "玻尿酸", "灌注", "bladder"]),
            ("oral", ["u101", "口服", "黏膜", "repair"]),
        ]
        for key, next_node in transitions.items():
            key_lower = key.lower()
            for group_name, keywords in keyword_groups:
                if any(keyword in user_input_lower for keyword in keywords):
                    if group_name == "hormone" and any(k in key_lower for k in ["雌激素", "賀爾蒙", "hormonal", "estrogen"]):
                        return next_node
                    if group_name == "ha" and any(k in key_lower for k in ["ha", "玻尿酸", "灌注", "bladder"]):
                        return next_node
                    if group_name == "oral" and any(k in key_lower for k in ["u101", "口服", "黏膜", "repair"]):
                        return next_node

        # 3.7. 從輸入中抓取數字（如「1到11」「選2」）
        number_match = re.search(r"([1-9])", user_input_lower)
        if number_match:
            index = int(number_match.group(1)) - 1
            transition_items = list(transitions.items())
            if 0 <= index < len(transition_items):
                return transition_items[index][1]

        # 4. 無下一節點 = 結束
        return None
    
    def build_reply(self, node: Dict[str, Any]) -> List[str]:
        """
        組合回覆訊息（問題 + 衛教文字）
        
        Returns:
            訊息列表（可包含多則）
        """
        messages = []
        
        # 主要問題
        prompt = node.get("prompt", "").strip()
        if prompt:
            messages.append(prompt)
        
        # 衛教文字（如果存在）
        education = node.get("education_text", "").strip()
        if education:
            messages.append(education)
        
        # 選項提示（如果有分支）
        transitions = node.get("transitions", {})
        if transitions:
            if "yes" in transitions and "no" in transitions:
                # 是/否題
                messages.append("請回覆「是」或「否」")
            elif len(transitions) > 0:
                # 多選題
                options_text = "、".join([f"「{k}」" for k in transitions.keys()])
                messages.append(f"請選擇：{options_text}")
        
        return messages if messages else ["感謝您的回覆！"]
    
    def get_all_nodes(self) -> List[Dict[str, Any]]:
        """取得所有節點（用於匯出報表）"""
        return list(self.nodes.values())
