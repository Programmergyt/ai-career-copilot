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
1. templates中的md和latex模板没有得到使用，并且main文件中输入的模板文件和tools\template_renderer.py也没有进行使用。应该让pipeline生成一个json格式的简历，最后再放入renderer中进行渲染。【已解决】
2. config.yaml的参数值没有真正被配置到程序中去。应该在config中添加变量，对于LLM、Embedding、Rerank模型，每种模型都需要有模型名、api_base、apikey的名称（假定环境变量中有对应名称的apikey）。完成变量添加后，就将config中的变量集体应用到程序中。【已解决】
3. project_analyzer，project_selector两个agent，分析用户给出的项目路径
