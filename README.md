# 测试脚本
conda activate rag_workflow
d:
cd D:\Py_Projects\ai-career-copilot 
python main.py --jd "D:\研究生\Agent测试\JD合集\SAP_AIGC工程师.md" --docs "D:\研究生\Agent测试\个人材料"
# 文件类型
- profile（基本信息，不参与RAG）
- project（个人项目信息，参与RAG）
- internship（实习项目信息，参与RAG）
- skill（个人技能以及掌握的知识点，参与RAG）
- paper（论文，参与RAG）
# 目前的问题与设想的解决
1. 目前是把project、intership、skill、paper放入同一个向量数据库中进行检索。最好改为分别放入4个数据库中，分别检索。如果完全没有一类文件（比如没有paper），简历中就不写paper，只要有一份文件，就要放入向量数据库、检索，放入简历。
