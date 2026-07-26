"""
DeepSeek R1深度分析工具
"""
from openai import AsyncOpenAI
import json
from typing import Dict, Any, Optional

from ..config import get_settings


R1_ANALYSIS_PROMPT_TEMPLATE = """你是一个旅行规划专家。请对以下旅行问题进行深度分析。

问题：
{problem}

上下文信息：
{context}

请进行深度推理，提供：
1. 问题分析
2. 约束条件
3. 优化建议
4. 多方案对比

输出JSON格式。
"""


class DeepSeekR1Analyzer:
    """DeepSeek R1深度分析器"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ):
        settings = get_settings()
        self.client = AsyncOpenAI(
            base_url=base_url or settings.deepseek_base_url,
            api_key=api_key or settings.deepseek_api_key,
        )
        self.model = model or settings.deepseek_reasoning_model
        self.temperature = temperature
    
    async def analyze(
        self,
        problem: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """深度分析复杂问题
        
        Args:
            problem: 需要分析的问题
            context: 上下文信息
            
        Returns:
            JSON格式的分析结果
        """
        prompt = R1_ANALYSIS_PROMPT_TEMPLATE.format(
            problem=problem,
            context=json.dumps(context or {}, ensure_ascii=False, indent=2)
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                extra_body={"thinking": {"type": "enabled"}},
            )
            
            return response.choices[0].message.content
        except Exception as e:
            error_result = {
                "analysis": f"分析失败: {str(e)}",
                "constraints": [],
                "suggestions": [],
                "reasoning": "无法完成深度分析"
            }
            return json.dumps(error_result, ensure_ascii=False)
    
    async def optimize_route(
        self,
        destinations: list,
        budget: float,
        days: int
    ) -> Dict[str, Any]:
        """优化旅行路线"""
        problem = f"""
        请优化以下旅行路线：
        - 目的地清单: {', '.join(destinations)}
        - 预算限制: {budget}元
        - 时间限制: {days}天
        
        要求：在预算和时间限制内，给出最优的游览顺序和每个地点的停留时间。
        """
        
        context = {
            "destinations": destinations,
            "budget": budget,
            "days": days
        }
        
        result = await self.analyze(problem, context)
        
        try:
            return json.loads(result)
        except (TypeError, json.JSONDecodeError):
            return {"error": "优化失败", "raw_response": result}
