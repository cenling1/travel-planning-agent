"""Reusable prompts for standalone tool wrappers."""

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
