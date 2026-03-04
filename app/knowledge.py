"""
知識庫模組 - 關鍵字匹配系統
"""
import os
import re
from typing import Optional, List, Dict

class KnowledgeBase:
    """關鍵字匹配的衛教知識庫"""
    
    def __init__(self, kb_path: str = "data/knowledge_base.txt"):
        self.kb_path = kb_path
        self.entries: List[Dict[str, any]] = []
        self.load()
    
    def load(self):
        """載入知識庫"""
        if not os.path.exists(self.kb_path):
            print(f"[KnowledgeBase] File not found: {self.kb_path}")
            return
        
        with open(self.kb_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析知識庫
        current_keywords = []
        current_reply = []
        
        for line in content.split('\n'):
            line = line.strip()
            
            if line.startswith('關鍵字:'):
                # 保存上一個 entry
                if current_keywords and current_reply:
                    self.entries.append({
                        'keywords': current_keywords,
                        'reply': '\n'.join(current_reply).strip()
                    })
                
                # 開始新的 entry
                keywords_text = line.replace('關鍵字:', '').strip()
                current_keywords = [k.strip() for k in keywords_text.split(',')]
                current_reply = []
                
            elif line.startswith('回覆:'):
                # 開始回覆內容
                current_reply.append(line.replace('回覆:', '').strip())
                
            elif line and current_reply:
                # 繼續回覆內容
                current_reply.append(line)
        
        # 保存最後一個 entry
        if current_keywords and current_reply:
            self.entries.append({
                'keywords': current_keywords,
                'reply': '\n'.join(current_reply).strip()
            })
        
        print(f"[KnowledgeBase] Loaded {len(self.entries)} entries")
    
    def search(self, user_input: str) -> Optional[str]:
        """
        搜尋知識庫
        根據關鍵字匹配回覆內容
        """
        if not self.entries:
            return None
        
        user_input_lower = user_input.lower()
        scores = []
        
        for entry in self.entries:
            score = 0
            matched_keywords = []
            
            for keyword in entry['keywords']:
                keyword_lower = keyword.lower()
                if keyword_lower in user_input_lower:
                    score += len(keyword_lower)  # 關鍵字越長分數越高
                    matched_keywords.append(keyword)
            
            if score > 0:
                scores.append((score, entry['reply'], matched_keywords))
        
        if scores:
            # 回覆分數最高的
            scores.sort(key=lambda x: x[0], reverse=True)
            best_match = scores[0]
            print(f"[KnowledgeBase] Matched: {best_match[2]}, score: {best_match[0]}")
            return best_match[1]
        
        return None


# 建立全域知識庫實例
knowledge_base = KnowledgeBase()
