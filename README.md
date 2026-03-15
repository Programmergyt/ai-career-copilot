# 测试脚本
conda activate rag_workflow
d:
cd D:\Py_Projects\ai-career-copilot 
python main.py --jd "D:\研究生\Agent测试\JD合集\SAP_AIGC工程师.md" --docs "D:\研究生\Agent测试\个人材料"

conda activate rag_workflow && D: && cd D:\Py_Projects\ai-career-copilot && python main.py --jd "D:\研究生\Agent测试\JD合集\SAP_AIGC工程师.md" --docs "D:\研究生\Agent测试\个人材料"


# 文件类型
- profile（基本信息，不参与RAG）
- project（个人项目信息，参与RAG）
- internship（实习项目信息，参与RAG）
- skill（个人技能以及掌握的知识点，参与RAG）
- paper（论文，参与RAG）

# 目前的问题与设想的解决
1. config.yaml的参数值没有真正被配置到程序中去。应该在config中添加变量，每个模型