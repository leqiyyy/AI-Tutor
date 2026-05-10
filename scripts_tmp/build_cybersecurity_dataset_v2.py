import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cybersecurity_rag_dataset.json"
DATASET_OUT = ROOT / "cybersecurity_rag_dataset_v2.json"
SPEC_OUT = ROOT / "backend" / "runtime_tmp" / "cybersecurity_benchmark_spec_v2.json"


BASE_RUBRIC = {
    "correctness": "回答应与标准答案的核心事实一致。",
    "completeness": "回答应覆盖 must_include 中列出的关键点。",
    "faithfulness": "回答只能依据课程资料和检索证据，不引入资料外事实。",
    "citation_consistency": "引用来源应命中 golden_sources 或 acceptable_sources。",
    "clarity": "回答应使用清晰的中文表述，结构适合课程学习场景。",
}


def _files_from_sources(sources):
    files = []
    for source in sources or []:
        file_name = source.get("file") or source.get("file_name")
        if file_name and file_name not in files:
            files.append(file_name)
    return files


def _focus(question_type, answerable=True):
    if not answerable:
        return ["refusal_accuracy", "faithfulness", "citation_consistency"]
    mapping = {
        "fact_extraction": ["retrieval", "correctness", "completeness", "citation_consistency"],
        "concept_explanation": ["retrieval", "correctness", "faithfulness", "clarity"],
        "comparison": ["retrieval", "correctness", "comparative_completeness", "citation_consistency"],
        "multi_modal": ["multimodal_retrieval", "correctness", "citation_consistency"],
        "image_question": ["image_evidence_retrieval", "correctness", "citation_consistency"],
        "table_question": ["table_evidence_retrieval", "correctness", "structure_completeness"],
        "formula_question": ["formula_evidence_retrieval", "correctness", "faithfulness"],
        "multi_hop_reasoning": ["multi_hop_retrieval", "reasoning_completeness", "faithfulness"],
        "cross_file_synthesis": ["cross_file_retrieval", "synthesis_quality", "citation_consistency"],
        "graph_relation": ["entity_relation_retrieval", "relationship_correctness", "citation_consistency"],
        "noise_resistant": ["noise_robustness", "correctness", "faithfulness"],
        "open_ended": ["synthesis_quality", "instruction_following", "faithfulness"],
    }
    return mapping.get(question_type, ["retrieval", "correctness", "faithfulness"])


def _discrimination(question_type, modality):
    if question_type in {"image_question", "table_question", "formula_question", "multi_modal"}:
        return "主要区分 mix 对多模态原子单元描述和文本证据联合检索的能力。"
    if question_type == "graph_relation":
        return "主要区分 local、global、hybrid、mix 对实体关系和知识图谱邻域的利用能力。"
    if question_type in {"multi_hop_reasoning", "cross_file_synthesis"}:
        return "主要区分 hybrid、mix 对跨证据组织和多跳关联的利用能力。"
    if question_type == "fact_extraction" and modality == "text":
        return "主要检验 naive 在直接文本片段召回中的基础能力。"
    if question_type == "unanswerable":
        return "主要检验回答生成阶段能否在证据不足时拒答。"
    return "用于观察不同检索模式在该类问题上的稳定性差异。"


def enrich(item):
    item = dict(item)
    qtype = item.get("question_type", "fact_extraction")
    answerable = bool(item.get("answerable", True))
    modality = item.get("expected_modality", "text")
    files = _files_from_sources(item.get("golden_sources", []))
    item.setdefault("acceptable_sources", files)
    item.setdefault("negative_sources", [])
    item.setdefault("evidence_granularity", "file_section")
    item.setdefault("evaluation_focus", _focus(qtype, answerable))
    item.setdefault("mode_discrimination", _discrimination(qtype, modality))
    item.setdefault("scoring_rubric", BASE_RUBRIC)
    return item


def src(file, location, snippet, modality="text", page="N/A", section=""):
    return {
        "file": file,
        "location": location,
        "snippet": snippet,
        "modality": modality,
        "page": page,
        "section": section or location,
    }


def q(
    qid,
    question,
    question_type,
    standard_answer,
    sources,
    keywords,
    difficulty,
    expected_modality,
    must_include,
    answerable=True,
    acceptable_sources=None,
    negative_sources=None,
    evidence_granularity="file_section",
):
    files = acceptable_sources or _files_from_sources(sources)
    return {
        "question_id": qid,
        "question": question,
        "question_type": question_type,
        "standard_answer": standard_answer,
        "golden_sources": sources,
        "acceptable_sources": files,
        "negative_sources": negative_sources or [],
        "keywords": keywords,
        "difficulty": difficulty,
        "expected_modality": expected_modality,
        "must_include": must_include,
        "answerable": answerable,
        "evidence_granularity": evidence_granularity,
        "evaluation_focus": _focus(question_type, answerable),
        "mode_discrimination": _discrimination(question_type, expected_modality),
        "scoring_rubric": BASE_RUBRIC,
    }


NEW_ITEMS = [
    q(
        "Q086",
        "分组交换中的存储转发传输是什么意思？为什么路由器缓存满时会发生丢包？",
        "graph_relation",
        "存储转发传输是指分组在链路输入端被完整接收后再继续转发，接收端再重新组装报文。路由器用排队等待的方式处理冲突，当缓存或等待队列已满时，后续到达的分组无法进入队列，因此会发生丢包。",
        [src("Markdown-1.md", "第一章 / 网络核心", "在链路的输入端对每个分组进行存储转发传输；用排队等待的方式处理数据冲突，如果路由器的缓存已满就会发生丢包。")],
        ["分组交换", "存储转发", "路由器缓存", "排队", "丢包"],
        "medium",
        "text",
        ["完整接收后转发", "重新组装", "排队等待", "缓存满", "丢包"],
    ),
    q(
        "Q087",
        "比较分组交换和电路交换在资源分配、连接建立和突发通信适应性上的差异。",
        "comparison",
        "分组交换按分组转发，不预留端到端资源，依靠排队和存储转发处理数据，更适合突发性计算机通信。电路交换会预留端到端资源，能够分配恒定速率，但建立连接耗时较长，空闲时仍占用资源，因此不适合突发流量。",
        [src("Markdown-1.md", "第一章 / 网络核心", "分组交换采用存储转发和排队等待；电路交换会预留端到端资源，建立连接耗时较长，不适合有突发性的计算机通信。")],
        ["分组交换", "电路交换", "资源预留", "突发通信", "存储转发"],
        "medium",
        "text",
        ["分组交换不预留端到端资源", "电路交换预留资源", "恒定速率", "连接建立耗时", "突发通信"],
    ),
    q(
        "Q088",
        "课程资料中的僵尸网络是什么？它通常怎样参与DDoS攻击？",
        "graph_relation",
        "僵尸网络是由大量被攻击设备组成、受攻击者控制和利用的网络。课程资料指出，它可被用于散布垃圾邮件或进行DDoS攻击。在DDoS场景中，被控制的主机通常充当代理主机或僵尸主机，按照攻击者命令向目标发送大量请求。",
        [
            src("Markdown-1.md", "第一章 / 网络攻击", "僵尸网络由数千个类似被攻击的设备组成，被坏人控制和利用来散布垃圾邮件或进行 DDoS 攻击。"),
            src("Word-5.docx", "第四章 / DDoS攻击过程", "在每台被入侵主机中安装攻击所用的客户进程或守护进程，向僵尸发送命令并向目标发起攻击。"),
        ],
        ["僵尸网络", "Botnet", "DDoS", "代理主机", "僵尸主机"],
        "medium",
        "text",
        ["大量被攻击设备", "受攻击者控制", "散布垃圾邮件", "DDoS攻击", "代理主机"],
    ),
    q(
        "Q089",
        "从知识图谱关系角度说明：僵尸网络、代理主机、DDoS攻击过程三者之间应形成怎样的关联？",
        "graph_relation",
        "三者可以形成“僵尸网络包含被控制主机、被控制主机可充当代理主机、代理主机参与DDoS攻击”的关系链。DDoS攻击过程先探测和入侵存在漏洞的主机，再安装代理程序或客户进程，最后由主控端发出命令，使代理主机向目标发起攻击。",
        [
            src("Markdown-1.md", "第一章 / 网络攻击", "僵尸网络由数千个类似被攻击的设备组成，被坏人控制和利用来散布垃圾邮件或进行 DDoS 攻击。"),
            src("Word-5.docx", "第四章 / DDoS攻击过程", "探测扫描大量主机；入侵有安全漏洞的主机并获取控制权；安装攻击所用的客户进程或守护进程；向僵尸发送命令。"),
        ],
        ["僵尸网络", "代理主机", "DDoS攻击过程", "控制关系", "攻击链"],
        "hard",
        "text",
        ["僵尸网络包含被控制主机", "代理主机", "探测扫描", "入侵控制", "主控命令"],
    ),
    q(
        "Q090",
        "HTTP为什么被称为无状态协议？Cookies由哪四个部分共同实现状态保持？",
        "fact_extraction",
        "HTTP被称为无状态协议，是因为服务器不维护关于客户的任何信息。Cookies通过四个部分实现状态保持：HTTP响应报文中的cookie首部行、HTTP请求报文中的cookie首部行、用户端系统中保留的cookie文件、Web后台数据库中的记录。",
        [src("Markdown-2.md", "第二章 / WEB和HTTP", "HTTP 是无状态的，意思是服务器不维护关于客户的任何信息；Cookies包含响应首部行、请求首部行、用户端cookie文件、Web后台数据库。")],
        ["HTTP", "无状态", "Cookies", "响应首部", "请求首部", "后台数据库"],
        "easy",
        "text",
        ["服务器不维护客户信息", "响应报文cookie首部", "请求报文cookie首部", "用户端cookie文件", "Web后台数据库"],
    ),
    q(
        "Q091",
        "非持久HTTP连接和持久HTTP连接在RTT消耗和TCP连接复用上有什么不同？",
        "comparison",
        "非持久HTTP连接中每个对象需要两个RTT，并且操作系统需要为每个TCP连接分配资源；持久HTTP连接在服务器发送响应后仍保持TCP连接，可使用同一连接传送后续请求和响应，客户端遇到引用对象时可以尽快发送请求。",
        [src("Markdown-2.md", "第二章 / WEB和HTTP", "非持久 HTTP 连接每个对象需要两个 RTT；持久 HTTP 连接在服务器发送响应后仍保持 TCP 连接，用相同连接传送后续请求和响应。")],
        ["非持久HTTP", "持久HTTP", "RTT", "TCP连接复用"],
        "medium",
        "text",
        ["每个对象两个RTT", "每个TCP连接分配资源", "保持TCP连接", "后续请求和响应", "尽快发送请求"],
    ),
    q(
        "Q092",
        "统一资源定位器URL由哪些部分组成？RTT在资料中如何定义？",
        "fact_extraction",
        "URL包括协议名、用户名、口令字、主机名、路径名和端口。RTT即往返时延，指数据从网络一端传到另一端所需的时间。",
        [src("Markdown-2.md", "第二章 / WEB和HTTP", "URL包括协议名、用户名、口令字、主机名、路径名、端口；RTT是数据从网络一端传到另一端所需的时间。")],
        ["URL", "协议名", "主机名", "路径名", "端口", "RTT"],
        "easy",
        "text",
        ["协议名", "用户名", "口令字", "主机名", "路径名", "端口", "RTT"],
    ),
    q(
        "Q093",
        "FTP协议为什么使用两个并行TCP连接？默认端口号是多少？",
        "fact_extraction",
        "FTP用于在远程主机之间上传或接收文件。它使用两个并行TCP连接：一个连接用于发送控制信息和用户认证，另一个连接用于实际传输文件。资料中给出的默认端口号是21。",
        [src("Markdown-2.md", "第二章 / WEB和HTTP", "FTP 使用两个并行 TCP 连接，一个用于发送控制信息进行用户认证，另一个用于实际传输文件；默认端口号 21。")],
        ["FTP", "TCP连接", "控制信息", "用户认证", "文件传输", "21端口"],
        "easy",
        "text",
        ["两个并行TCP连接", "控制信息", "用户认证", "实际传输文件", "默认端口21"],
    ),
    q(
        "Q094",
        "POP协议和IMAP协议在客户端操作是否反馈到服务器方面有什么区别？",
        "comparison",
        "POP协议允许电子邮件客户端下载服务器上的邮件，但客户端操作不会反馈到服务器上；IMAP协议支持在服务器上创建或更改文件夹或邮箱，客户端对邮件状态的操作会与服务器保持一致，并支持联机和断连接操作。",
        [
            src("Markdown-2.md", "第二章 / 因特网中的电子邮件", "POP允许客户端下载服务器上的邮件，但是客户端操作不会反馈到服务器；IMAP可以在服务器上创建或更改文件夹或邮箱，支持联机和断连接操作。"),
            src("Markdown-3.md", "TCP/IP协议族 / 邮件协议", "POP3协议允许客户端下载服务器上的邮件，但是客户端上的操作并不会反馈到服务器；IMAP对客户端的操作会反馈到服务端。"),
        ],
        ["POP", "IMAP", "邮件协议", "服务器反馈", "邮件状态"],
        "medium",
        "text",
        ["POP客户端操作不反馈服务器", "IMAP操作反馈服务器", "服务器文件夹", "联机操作", "断连接操作"],
    ),
    q(
        "Q095",
        "DNS在应用层资料中承担什么功能？默认使用哪个传输层协议和端口？",
        "fact_extraction",
        "DNS负责将有意义的字符串网址转换为二进制网络地址，是将域名和IP地址相互映射的分布式数据库，使用户更方便地访问互联网。资料中给出DNS使用UDP端口53。",
        [src("Markdown-2.md", "第二章 / DNS", "DNS负责将有意义的字符串网址转换为二进制的网络地址，是域名和IP地址相互映射的分布式数据库，使用 UDP 端口 53。")],
        ["DNS", "域名", "IP地址", "分布式数据库", "UDP", "53端口"],
        "easy",
        "text",
        ["字符串网址转换", "域名和IP映射", "分布式数据库", "UDP", "53端口"],
    ),
    q(
        "Q096",
        "结合应用层协议资料和Web安全资料，说明HTTPS相对HTTP增加了哪些安全能力。",
        "cross_file_synthesis",
        "HTTP以明文方式传输内容，不提供数据加密。HTTPS在HTTP基础上加入SSL，SSL依靠证书验证服务器身份，并位于传输层协议和应用层协议之间。应用层资料还指出，带有SSL的TCP可提供加密、数据完整性和端点认证，因此HTTPS相对HTTP主要增强了机密性、完整性和身份认证能力。",
        [
            src("Markdown-3.md", "TCP/IP协议族 / HTTP与HTTPS", "HTTP协议以明文的方式发送内容；HTTPS在HTTP协议的基础上加入SSL协议，SSL依靠证书来验证服务器的身份。"),
            src("Markdown-2.md", "第二章 / SSL", "带有 SSL 的 TCP 可以提供加密、数据完整性和端点认证。"),
        ],
        ["HTTP", "HTTPS", "SSL", "证书", "加密", "完整性", "端点认证"],
        "hard",
        "text",
        ["HTTP明文", "HTTPS加入SSL", "证书验证服务器身份", "加密", "数据完整性", "端点认证"],
    ),
    q(
        "Q097",
        "SSL在资料中被描述为什么层次的增强？它可以提供哪些进程对进程安全服务？",
        "fact_extraction",
        "资料说明SSL不是与TCP、UDP同级的第三种互联网传输协议，而是对TCP的增强；SSL在应用层、TCP之上。带有SSL的TCP可以提供加密、数据完整性和端点认证等进程对进程安全服务。",
        [src("Markdown-2.md", "第二章 / SSL", "SSL不是与TCP和UDP同级的第三种互联网传输协议，而是对TCP的增强；SSL在应用层，在TCP之上；提供加密、数据完整性和端点认证。")],
        ["SSL", "TCP增强", "应用层", "加密", "数据完整性", "端点认证"],
        "medium",
        "text",
        ["不是第三种传输协议", "对TCP的增强", "在TCP之上", "加密", "数据完整性", "端点认证"],
    ),
    q(
        "Q098",
        "DASH、CDN和集群选择策略在视频流媒体分发中分别承担什么作用？",
        "multi_hop_reasoning",
        "DASH将视频编码为多个不同版本，每个版本具有不同码率，使用户能动态请求不同版本的视频段；CDN管理多个地理位置的服务器，存储视频并将用户请求导向体验更好的位置；集群选择策略负责动态地将客户定向到CDN中的某个服务器集群或数据中心。",
        [src("Markdown-2.md", "第二章 / 视频流和内容分发网", "DASH将视频编码为几个不同版本；CDN管理分布在多个地理位置的服务器；集群选择策略动态地将客户定向到CDN中的服务器集群或数据中心。")],
        ["DASH", "CDN", "集群选择策略", "码率", "视频段", "服务器集群"],
        "hard",
        "text",
        ["不同码率版本", "动态请求视频段", "分布式服务器", "最佳体验位置", "服务器集群"],
    ),
    q(
        "Q099",
        "为什么资料说TCP/IP不仅仅指TCP和IP两种协议？",
        "concept_explanation",
        "资料指出，TCP/IP并不只是TCP和IP两种协议，而是一系列网络协议的总和。TCP和IP是其中最核心的两个协议，因此该协议族被称为TCP/IP网络协议族，它构成互联网的基础通信架构。",
        [src("Markdown-3.md", "TCP/IP", "TCP/IP不仅仅是指TCP和IP这两种协议，而是一系列网络协议的总和；最核心的两个协议就是TCP和IP。")],
        ["TCP/IP", "协议族", "TCP", "IP", "互联网基础通信架构"],
        "easy",
        "text",
        ["一系列网络协议", "TCP和IP是核心协议", "TCP/IP网络协议族", "互联网基础通信架构"],
    ),
    q(
        "Q100",
        "根据TCP/IP资料，HTTP与HTTPS在传输安全性上有什么区别？",
        "comparison",
        "HTTP用于Web浏览器和Web服务器之间传递数据，但以明文方式发送内容，不提供数据加密，因此安全性较弱。HTTPS在HTTP基础上加入SSL协议，SSL依靠证书验证服务器身份，使传输更安全。",
        [src("Markdown-3.md", "TCP/IP协议族 / HTTP与HTTPS", "HTTP以明文方式发送内容，不提供数据加密；HTTPS在HTTP基础上加入SSL，SSL依靠证书验证服务器身份。")],
        ["HTTP", "HTTPS", "明文", "SSL", "证书", "服务器身份"],
        "easy",
        "text",
        ["HTTP明文", "不提供数据加密", "HTTPS加入SSL", "证书验证", "服务器身份"],
    ),
    q(
        "Q101",
        "TCP资料中列出了哪些保证可靠传输的机制？请至少说明三项。",
        "fact_extraction",
        "资料列出的TCP可靠传输机制包括校验和、确认应答ACK与序列号、超时重传、连接管理、流量控制和拥塞控制。校验和用于发现传输错误，ACK和序列号用于确认接收位置，超时重传用于处理数据包丢失。",
        [src("Markdown-3.md", "TCP如何保证可靠性传输", "校验和、确认应答ACK和序列号、超时重传、连接管理、流量控制、拥塞控制。")],
        ["TCP可靠性", "校验和", "ACK", "序列号", "超时重传", "流量控制", "拥塞控制"],
        "medium",
        "text",
        ["校验和", "ACK", "序列号", "超时重传", "流量控制", "拥塞控制"],
    ),
    q(
        "Q102",
        "TCP为什么会出现粘包或半包问题？资料给出了哪些解决消息边界的方法？",
        "fact_extraction",
        "TCP是面向字节流的协议，消息本身没有边界，因此可能出现粘包或半包。资料给出的解决方法包括固定长度、添加分隔符、添加数据长度字段。UDP的每个消息有边界，因此不会出现同样的粘包和半包问题。",
        [src("Markdown-3.md", "TCP消息无边界", "TCP没有消息边界；解决办法有固定长度、分隔符、添加数据的长度字段；UDP每个消息都是有边界的。")],
        ["TCP", "粘包", "半包", "消息边界", "固定长度", "分隔符", "长度字段"],
        "medium",
        "text",
        ["面向字节流", "没有消息边界", "固定长度", "分隔符", "长度字段", "UDP有边界"],
    ),
    q(
        "Q103",
        "结合TCP三次握手和SYN Flood资料，说明SYN Flood为什么能利用连接建立阶段消耗服务器资源。",
        "cross_file_synthesis",
        "TCP连接建立依赖SYN、SYN-ACK和ACK三次握手。SYN Flood利用这一阶段，攻击者大量发送SYN请求，使服务器为半连接分配资源并等待最终ACK。如果大量半连接不能完成，就会占用服务器连接队列和内存，影响正常连接建立。",
        [
            src("Markdown-3.md", "TCP三次握手", "三次握手后，客户端和服务端进入ESTABLISHED状态并可以传输数据。"),
            src("PDF-2.pdf", "网络攻击行径分析 / SYN Flood", "正常TCP三次握手与SYN Flood攻击流程对比。"),
            src("图片-3.png", "图2 TCP的连接过程", "序列图展示客户端、服务器、ACK标志位和被防火墙阻止的连接。", "image"),
        ],
        ["TCP三次握手", "SYN", "SYN-ACK", "ACK", "SYN Flood", "半连接"],
        "hard",
        "mixed",
        ["SYN", "SYN-ACK", "ACK", "半连接", "资源占用", "连接队列"],
    ),
    q(
        "Q104",
        "Web介绍课件中，Web的基本结构包含哪些角色？浏览器和Web服务器分别承担什么任务？",
        "fact_extraction",
        "Web是运行于Internet和TCP/IP之上的基本Client/Server应用，并从C/S演化为B/S。浏览器作为客户机向服务器发送资源请求，并将接收到的信息解码和显示；Web服务器规定传输设定、信息传输格式和开放结构，并常与数据库交互。",
        [src("PPT-1-Web介绍.pptx", "Web的基本结构", "Web是运行于Internet和TCP/IP之上的client/server应用；客户机统称Web浏览器，用于发送资源请求并显示信息；WebServer后常与数据库打交道。")],
        ["Web基本结构", "B/S", "浏览器", "Web服务器", "数据库"],
        "easy",
        "text",
        ["Client/Server", "Browser/Server", "浏览器发送请求", "解码和显示", "WebServer", "数据库"],
    ),
    q(
        "Q105",
        "Web介绍课件中的HTTP工作过程包括哪些步骤？默认端口是什么？",
        "fact_extraction",
        "HTTP工作过程中，Web服务器在80端口等待浏览器请求；浏览器通过三次握手与服务器建立TCP/IP连接；随后浏览器向服务器发送索取页面的请求；服务器以相应文件为内容响应浏览器请求。",
        [src("PPT-1-Web介绍.pptx", "HTTP工作过程", "Web服务器在80端口等候Web浏览器请求；Web浏览器通过三次握手与服务器建立TCP/IP连接，然后发送索取页面的请求，服务器响应。")],
        ["HTTP", "80端口", "三次握手", "页面请求", "服务器响应"],
        "medium",
        "text",
        ["80端口", "三次握手", "TCP/IP连接", "索取页面请求", "服务器响应"],
    ),
    q(
        "Q106",
        "根据Web基本结构图，说明B/S模型中的浏览器、Web服务器和数据库之间的关系。",
        "image_question",
        "图中B/S模型将浏览器放在客户端，将Web服务器放在服务器端，服务器端还连接数据库。浏览器向Web服务器发起请求，Web服务器处理请求并在需要时访问数据库，再将结果返回浏览器显示。",
        [
            src("PPT-1-Web介绍.pptx", "Web基本结构图", "图示展示Browser/Server模型，浏览器位于客户端，服务器端包括Web Server和数据库。", "image"),
            src("PPT-1-Web介绍.pptx", "Web的基本结构", "客户为浏览器，服务器为WebServer，WebServer后常常与数据库打交道。"),
        ],
        ["B/S模型", "浏览器", "Web服务器", "数据库", "请求响应"],
        "medium",
        "mixed",
        ["浏览器", "WebServer", "数据库", "请求", "响应"],
    ),
    q(
        "Q107",
        "Web威胁课件为什么认为Web应用可能成为攻击者进入内部网络的入口？",
        "fact_extraction",
        "课件指出Web是开放服务，可能成为攻击者的主要攻击目标或进入内部网络的入口；Web应用系统可能包含丰富资料；Client-Server架构中的资料传输可能经过不安全网络路径，攻击者可拦截、窃取或篡改数据。",
        [src("PPT-2-Web威胁.pptx", "Web安全威胁", "Web为开放服务，可能成为攻击者主要攻击目标或进入内部网络的进入点；Web应用系统可能包含丰富资料；资料传输可能经过不安全网络路径。")],
        ["Web安全威胁", "开放服务", "内部网络入口", "资料", "拦截", "窃取", "篡改"],
        "medium",
        "text",
        ["开放服务", "攻击目标", "内部网络入口", "丰富资料", "不安全网络路径"],
    ),
    q(
        "Q108",
        "根据OWASP Top 10对照表，2013版到2017版中哪些风险保持稳定，哪些风险被新增或合并？",
        "table_question",
        "表格显示，注入风险从2013版A1延续为2017版A1，使用含有已知漏洞的组件也从A9延续为A9。2017版新增或变化的项目包括XML外部实体、失效的访问控制、不安全的反序列化、不足的日志记录和监控；2013版中的不安全直接对象引用与功能级访问控制缺失发生合并或调整。",
        [src("PPT-2-Web威胁.pptx", "OWASP Top 10对照表", "2013年版与2017年版OWASP Top 10对照：A1注入保持，A9使用含有已知漏洞的组件保持，XXE、不安全反序列化、不足日志记录和监控为2017版变化项。", "table")],
        ["OWASP Top 10", "注入", "XXE", "不安全反序列化", "已知漏洞组件", "日志记录和监控"],
        "hard",
        "table",
        ["A1注入", "A9已知漏洞组件", "XML外部实体", "失效的访问控制", "不安全反序列化", "不足日志记录和监控"],
    ),
    q(
        "Q109",
        "根据TCP目的端口流量排名图，排名靠前的Web相关端口有哪些？这说明Web服务流量有什么特点？",
        "image_question",
        "图中TCP目的端口流量排名里，80端口排名最高，443端口也位于前列。80对应HTTP，443对应HTTPS，说明Web访问和Web安全通信在网络流量中占有显著比例，是Web安全防护需要重点关注的对象。",
        [src("PPT-2-Web威胁.pptx", "TCP目的端口流量排名图", "图中80端口具有最长条形，443端口也有明显流量条，标题为TCP目的端口流量排名。", "image")],
        ["TCP目的端口", "80端口", "443端口", "HTTP", "HTTPS", "Web流量"],
        "medium",
        "image",
        ["80端口", "443端口", "HTTP", "HTTPS", "Web流量占比高"],
    ),
    q(
        "Q110",
        "SQL Injection课件如何定义SQL注入？为什么说它主要属于Input Validation问题？",
        "fact_extraction",
        "课件把SQL Injection称为SQL指令植入式攻击，强调它不是植入计算机病毒，而是利用写入特殊SQL程序码攻击应用程序。只要存在用户输入界面，并且没有严格控制输入资料类型，就可能遭受这种攻击，因此它主要属于Input Validation问题。",
        [src("PPT-3-SQL-Injection介绍.pptx", "什么是SQL Injection", "SQLInjection应称为SQL指令植式攻击，主要属于InputValidation问题；并非植入计算机病毒，而是利用写入特殊SQL程序码攻击应用程序。")],
        ["SQL Injection", "SQL注入", "Input Validation", "输入验证", "特殊SQL程序码"],
        "easy",
        "text",
        ["SQL指令植入式攻击", "Input Validation", "不是计算机病毒", "特殊SQL程序码", "用户输入界面"],
    ),
    q(
        "Q111",
        "根据SQL Injection攻击流程图，攻击者、攻击机器、Web服务器和MS-SQL数据库之间的攻击路径是什么？",
        "image_question",
        "图中攻击者先向攻击机器发起操作，再经由攻击机器向目标Web服务器提交带有特殊SQL语句的请求，Web服务器将请求传递给后端MS-SQL数据库执行，攻击结果再沿相反路径返回。该图强调SQL注入通过Web应用输入点影响后端数据库查询。",
        [src("PPT-3-SQL-Injection介绍.pptx", "SQL Injection攻击流程图", "图示包括Attacker、Attack Machine、Web Server和MS-SQL Database，箭头表示攻击请求进入Web服务器并影响数据库。", "image")],
        ["SQL注入流程图", "Attacker", "Attack Machine", "Web Server", "MS-SQL Database"],
        "hard",
        "image",
        ["攻击者", "攻击机器", "Web服务器", "MS-SQL数据库", "特殊SQL请求"],
    ),
    q(
        "Q112",
        "课件中的登录绕过示例为什么能够在已知Admin账号时不输入密码进入数据库？",
        "fact_extraction",
        "示例中的应用将用户输入直接拼接进SQL语句。攻击者在用户名或密码位置构造使条件恒真的片段，例如利用OR 1=1类条件，就可能使WHERE子句绕过真实密码校验。核心原因是程序没有把输入当作数据处理，而是让输入参与了SQL语句结构。",
        [src("PPT-3-SQL-Injection介绍.pptx", "SQL Injection原理", "select * from member where UID=... And Passwd=...；若攻击者已知Admin账号，则输入Admin，即可不须输入密码而进入数据库。")],
        ["登录绕过", "Admin", "OR 1=1", "SQL拼接", "WHERE条件"],
        "medium",
        "text",
        ["用户输入拼接SQL", "Admin账号", "条件恒真", "绕过密码校验", "输入验证不足"],
    ),
    q(
        "Q113",
        "防SQL Injection课件列出的输入处理和权限控制措施有哪些？",
        "fact_extraction",
        "课件列出的措施包括：将使用者输入作为参数传给SQL的Stored Procedure；使用Regular Expression验证输入格式；限制输入长度；限制登录数据库账号的权限；去除输入中的SQL注释符号“--”；将输入中的单引号置换成双引号。",
        [src("PPT-4-防止SQL-Injection.pptx", "防SQL Injection攻击的基本原则", "将使用者输入资料当做参数传给SQL的StoredProcedure；使用RegularExpression验证输入格式；限制长度；限制数据库账号权限；去除“--”；替换单引号。")],
        ["SQL注入防御", "Stored Procedure", "Regular Expression", "输入长度", "权限控制", "SQL注释"],
        "medium",
        "text",
        ["Stored Procedure", "Regular Expression", "限制输入长度", "限制数据库账号权限", "去除--", "替换单引号"],
    ),
    q(
        "Q114",
        "根据课件中的SQL语句示例，为什么输入 `or 1=1` 会影响查询结果？替换单引号后结果为什么变化？",
        "formula_question",
        "示例SQL原本用于统计满足UserName和Password条件的成员数量。输入包含单引号和 `or 1=1` 时，如果直接拼接，WHERE条件可能被改写为恒真，从而返回Members表总笔数。将用户输入的单引号替换成双引号后，攻击片段不再改变SQL结构，示例结果变为0。",
        [src("PPT-4-防止SQL-Injection.pptx", "单引号替换示例", "未将使用者输入的单引号置换成双引号，SQL执行结果为Members资料表总笔数；置换后执行结果为0。", "formula")],
        ["or 1=1", "SQL条件", "单引号", "双引号", "Members", "查询结果"],
        "hard",
        "formula",
        ["WHERE条件恒真", "返回总笔数", "单引号改变SQL结构", "替换双引号", "结果为0"],
    ),
    q(
        "Q115",
        "结合SQL注入介绍和防御课件，说明SQL注入的根因和对应防御策略之间的对应关系。",
        "cross_file_synthesis",
        "SQL注入的根因是应用把用户输入直接拼接到SQL语句中，并且没有严格进行输入验证。对应防御策略是把输入作为参数传给SQL或存储过程，使用正则表达式验证格式，限制输入长度，降低数据库账号权限，过滤注释符和特殊引号，避免输入改变SQL语句结构。",
        [
            src("PPT-3-SQL-Injection介绍.pptx", "什么是SQL Injection", "只要提供给使用者输入的界面，又没有做到严密的输入资料型态管制，就可能遭受攻击。"),
            src("PPT-4-防止SQL-Injection.pptx", "防SQL Injection攻击的基本原则", "参数化StoredProcedure、RegularExpression、限制长度、限制权限、去除注释符、替换单引号。"),
        ],
        ["SQL注入根因", "输入验证", "参数化", "权限控制", "特殊字符过滤"],
        "hard",
        "text",
        ["直接拼接输入", "输入验证不足", "参数化", "正则验证", "限制权限", "特殊字符处理"],
    ),
    q(
        "Q116",
        "XSS课件如何定义跨站脚本攻击？它可能造成哪些危害？",
        "fact_extraction",
        "XSS是攻击者利用站点程序对用户输入过滤不足的缺陷，输入可显示在页面上或影响其他用户的HTML/脚本代码。其危害包括盗取用户资料、利用用户身份执行动作、对访问者进行病毒侵害，以及通过恶意JavaScript控制浏览器行为。",
        [src("PPT-5-XSS攻击介绍.pptx", "Cross-Site Scripting(XSS)", "XSS攻击是攻击者利用站程序对用户输入过滤不足的缺陷，输入可以显示在页面上或影响其他用户的HTML代码，从而盗取用户资料、利用用户身份进行动作或对访问者进行病毒侵害。")],
        ["XSS", "跨站脚本", "用户输入过滤", "HTML代码", "JavaScript", "Cookie"],
        "easy",
        "text",
        ["用户输入过滤不足", "恶意HTML或脚本", "盗取用户资料", "利用用户身份", "控制浏览器"],
    ),
    q(
        "Q117",
        "反射型XSS、存储型XSS和DOM型XSS在交互路径和危害稳定性上有何不同？",
        "comparison",
        "反射型XSS主要发生在浏览器与服务器交互中，用户输入通过URL等形式直接输出，通常需要诱骗用户触发。存储型XSS涉及浏览器、服务器和数据库交互，恶意数据被保存到服务端，用户访问页面时触发，危害范围更大且稳定性更强。DOM型XSS由JavaScript DOM节点编程改变HTML代码形成，需要针对具体DOM代码分析。",
        [src("PPT-5-XSS攻击介绍.pptx", "XSS分类", "反射型XSS：浏览器—服务器交互；存储型XSS：浏览器—服务器—数据库交互，可直接产生大范围危害，稳定性较强；DOM型XSS由JavaScript DOM节点编程改变HTML代码形成。")],
        ["反射型XSS", "存储型XSS", "DOM型XSS", "浏览器", "服务器", "数据库"],
        "medium",
        "text",
        ["反射型浏览器服务器交互", "存储型浏览器服务器数据库交互", "存储型稳定性强", "DOM节点编程", "诱骗触发"],
    ),
    q(
        "Q118",
        "根据XSS攻击手法图，存储型XSS中攻击者、Web Server和Client之间的执行流程是什么？",
        "image_question",
        "图中攻击者向Web Server注入恶意脚本，Web Server保存或返回包含恶意脚本的内容，多个Client访问页面时接收并执行该脚本。该流程体现了存储型XSS通过服务端传播到多个客户端的特点。",
        [src("PPT-5-XSS攻击介绍.pptx", "XSS攻击手法图", "图示包含Attacker、Web Server和多个Client，红色箭头表示Malicious script被注入服务器并影响客户端。", "image")],
        ["XSS攻击手法", "存储型XSS", "Attacker", "Web Server", "Client", "恶意脚本"],
        "hard",
        "image",
        ["攻击者注入脚本", "Web Server", "多个Client", "客户端执行", "存储型传播"],
    ),
    q(
        "Q119",
        "XSS课件中的测试URL和Cookie窃取示例说明了什么攻击风险？",
        "fact_extraction",
        "测试URL在参数中加入JavaScript，如果弹出警告窗口，说明该URL参数存在XSS弱点。Cookie窃取示例说明，查询字符串中的JavaScript可以把用户Cookie发送到远端恶意网站，从而导致身份凭据或会话信息泄漏。",
        [src("PPT-5-XSS攻击介绍.pptx", "XSS原理", "在URL中加入JavaScript，若弹出警告视窗，则表示该URL参数具有XSS弱点；查询字符串中包含JavaScript会将使用者Cookie送到远端恶意网站。")],
        ["XSS测试URL", "alert", "Cookie", "恶意网站", "会话泄漏"],
        "medium",
        "text",
        ["URL参数", "JavaScript", "弹出警告", "Cookie发送到恶意网站", "会话信息泄漏"],
    ),
    q(
        "Q120",
        "课件给出的消除XSS漏洞通常思路是什么？为什么单纯过滤字符存在局限？",
        "fact_extraction",
        "课件给出的思路是对用户输入内容进行过滤，过滤掉可能产生危害的字符，例如尖括号和引号。但局限在于Web应用需要合理处理所有用户输入很困难，所有不被信任的内容都必须经过处理，而浏览器可能以服务器未预期的方式解释执行内容。",
        [src("PPT-5-XSS攻击介绍.pptx", "消除XSS漏洞通常思路", "对用户输入内容进行过滤，过滤掉可能产生危害的字符；局限性是合理处理所有用户输入很困难，不被信任的内容都必须经过处理。")],
        ["XSS防御", "输入过滤", "不可信内容", "浏览器解释", "过滤局限性"],
        "medium",
        "text",
        ["过滤用户输入", "尖括号", "引号", "不可信内容", "浏览器解释差异", "局限性"],
    ),
    q(
        "Q121",
        "从图谱关系角度说明：Teardrop攻击为什么与IP分片重组、偏移量重叠和资源消耗有关？",
        "graph_relation",
        "Teardrop攻击利用IP分片信息异常。资料描述第一个包偏移量为0、长度为N，第二个包偏移量小于N，导致分片范围重叠。系统在合并这些数据段时可能分配异常多资源，造成资源缺乏、重启或崩溃。因此图谱中可形成“Teardrop攻击—利用—分片偏移重叠—导致—资源消耗/系统崩溃”的关系链。",
        [src("word-1.docx", "第二章 / DoS常见类型和手段", "Teardrop第一个包的偏移量为0，长度为N，第二个包的偏移量小于N；合并这些数据段会分配超乎寻常的巨大资源，造成系统资源缺乏甚至机器重启。")],
        ["Teardrop", "IP分片", "偏移量", "重叠", "资源消耗", "系统崩溃"],
        "hard",
        "text",
        ["偏移量为0", "第二个包偏移量小于N", "分片重叠", "资源消耗", "系统重启或崩溃"],
    ),
    q(
        "Q122",
        "交换机缓冲区溢出为什么会增加交换式以太网中的监听风险？",
        "graph_relation",
        "交换机依赖MAC地址与端口映射表进行存储转发。若攻击者用大量无效IP包或错误MAC地址帧攻击交换机，交换机处理器繁忙，数据包来不及转发，缓冲区溢出并产生丢包。资料指出此时交换机可能退回到HUB广播方式，把数据包发送到所有端口，从而增加被监听的风险。",
        [src("Word-3.docx", "网络监听 / 交换式以太网", "交换机维护MAC地址与端口映射表；大量无效IP包和错误MAC地址帧会造成缓冲区溢出；交换机退回到HUB广播方式，向所有端口发送数据包。")],
        ["交换机缓冲区溢出", "MAC地址表", "HUB广播", "网络监听", "交换式以太网"],
        "hard",
        "text",
        ["MAC地址端口映射表", "错误MAC地址帧", "缓冲区溢出", "退回HUB广播方式", "监听风险"],
    ),
    q(
        "Q123",
        "ARP响应的服务器级检测方法为什么要使用RARP？",
        "graph_relation",
        "服务器收到ARP响应后，可根据响应报文中的MAC地址生成RARP请求，询问该MAC地址对应的IP地址。若RARP查询到的IP地址与ARP响应中声称的IP地址不同，就说明对方可能伪造了ARP响应报文。",
        [src("Word-3.docx", "ARP欺骗检测 / 服务器级检测", "服务器收到ARP响应时，根据RARP用响应报文给出的MAC地址生成RARP请求，查询该MAC地址对应IP，若两个IP不同，则说明对方伪造ARP响应报文。")],
        ["ARP响应", "RARP", "MAC地址", "IP地址", "服务器级检测", "伪造ARP"],
        "medium",
        "text",
        ["收到ARP响应", "根据MAC生成RARP请求", "查询对应IP", "比较两个IP", "伪造ARP响应"],
    ),
    q(
        "Q124",
        "Unicast Reverse Path Forwarding在DoS防范中用于解决什么问题？",
        "graph_relation",
        "资料将Unicast Reverse Path Forwarding作为检查访问者来源的方法。它通过反向路由查询检查访问者IP地址是否真实，若发现是假IP地址则进行屏蔽，从而减少攻击中伪造源IP地址的问题。",
        [src("Word-3.docx", "DoS攻击防范方法", "使用Unicast Reverse Path Forwarding等通过反向路由器查询的方法检查访问者的IP地址是否真，如果是假的，它将予以屏蔽。")],
        ["Unicast Reverse Path Forwarding", "反向路由", "源地址检查", "假IP", "DoS防范"],
        "medium",
        "text",
        ["反向路由查询", "检查IP真实性", "屏蔽假IP", "减少伪造源地址", "DoS防范"],
    ),
    q(
        "Q125",
        "网卡、网络隔离卡和网闸分别工作在什么隔离思路下？它们的安全边界有何不同？",
        "comparison",
        "网卡是链路层网络组件，用于连接计算机和传输介质，更多体现网络接入能力。网络隔离卡属于物理层隔离思路，同一时刻数据只能通往一个分区，切换内外网通常需要状态转换。网闸强调在保证安全的基础上进行数据交换，采用双主机架构，安全级别高于普通防火墙。",
        [
            src("Word-3.docx", "网卡与网络隔离卡的区别", "网卡是工作在链路层的网络组件；网络隔离卡专网专用，内网和外网系统分离。"),
            src("Word-3.docx", "网闸与防火墙的区别", "防火墙首先保证网络连通性，然后考虑安全问题；网闸在保证安全基础上进行数据交换，是双主机架构。"),
        ],
        ["网卡", "网络隔离卡", "网闸", "链路层", "物理隔离", "双主机架构"],
        "hard",
        "text",
        ["网卡链路层", "隔离卡物理隔离", "同一时刻通往一个分区", "网闸保证安全后交换", "双主机架构"],
    ),
    q(
        "Q126",
        "Word-4中给出的硬件漏洞和软件漏洞例子分别是什么？",
        "fact_extraction",
        "硬件漏洞例子是向电脑CPU刷入恶意Firmware固件，使未经许可的攻击者进入系统且管理员难以发现。软件漏洞例子包括XSS跨站脚本、注入、跨站指令和Cookie相关问题。",
        [src("Word-4.docx", "概述 / 硬件软件漏洞例子", "硬件：给CPU刷入恶意Firmware固件；软件：XSS跨站脚本、注入、跨站指令cookie等。")],
        ["硬件漏洞", "Firmware", "CPU", "软件漏洞", "XSS", "注入", "Cookie"],
        "easy",
        "text",
        ["恶意Firmware", "CPU", "未经许可进入系统", "XSS", "注入", "Cookie"],
    ),
    q(
        "Q127",
        "Web应用防火墙WAF在Word-4资料中承担什么作用？它保护的是哪类流量？",
        "graph_relation",
        "资料说明Web应用防火墙WAF通过执行一系列针对HTTP/HTTPS的安全策略，专门为Web应用提供保护。它主要面向HTTP和HTTPS Web应用流量，用于作为Web应用安全防护技术手段。",
        [src("Word-4.docx", "事前防御 / Web应用防火墙", "Web应用防火墙WAF是通过执行一系列针对HTTP/HTTPS的安全策略来专门为Web应用提供保护的安全防护技术手段。")],
        ["WAF", "Web应用防火墙", "HTTP", "HTTPS", "安全策略", "Web应用"],
        "medium",
        "text",
        ["HTTP/HTTPS", "安全策略", "Web应用", "专门保护", "防护技术手段"],
    ),
    q(
        "Q128",
        "结合WAF、SQL注入防御和XSS防御资料，设计一个Web应用纵深防御思路。",
        "cross_file_synthesis",
        "纵深防御可以分三层：入口层通过WAF执行HTTP/HTTPS安全策略；应用输入层使用参数化、正则验证、长度限制、特殊字符处理和最小数据库权限防御SQL注入；页面输出层对不可信内容进行处理，过滤可能触发XSS的字符，并避免用户输入未经处理直接进入页面。",
        [
            src("Word-4.docx", "Web应用防火墙WAF", "WAF通过针对HTTP/HTTPS的安全策略专门为Web应用提供保护。"),
            src("PPT-4-防止SQL-Injection.pptx", "防SQL Injection攻击的基本原则", "参数化StoredProcedure、RegularExpression、限制长度、权限控制、去除注释符、替换单引号。"),
            src("PPT-5-XSS攻击介绍.pptx", "消除XSS漏洞通常思路", "对用户输入内容进行过滤，所有不被信任的内容都必须经过处理。"),
        ],
        ["WAF", "SQL注入防御", "XSS防御", "参数化", "输入过滤", "纵深防御"],
        "hard",
        "text",
        ["WAF", "HTTP/HTTPS安全策略", "参数化", "正则验证", "权限控制", "不可信内容处理"],
    ),
    q(
        "Q129",
        "资料中提到ARP欺骗的破绽特征是什么？可以用什么工具或方式观察？",
        "graph_relation",
        "资料指出ARP欺骗的特征是不断发送ARP包，使被攻击主机相信并修改ARP表。可以使用Wireshark观察ARP包和ARP表变化，检测并过滤伪造ARP报文，建立正确的ARP映射关系。",
        [src("Word-4.docx", "网络扫描/侦察技术 / ARP欺骗", "ARP欺骗的特征就是不断发ARP包，让被攻击主机相信并修改ARP表；使用wireshark观察。")],
        ["ARP欺骗", "ARP包", "ARP表", "Wireshark", "伪造ARP报文"],
        "medium",
        "text",
        ["不断发送ARP包", "修改ARP表", "Wireshark", "过滤伪造ARP", "正确ARP映射"],
    ),
    q(
        "Q130",
        "从访问控制关系看，DAC、MAC和RBAC分别解决什么问题？为什么RBAC仍有不足？",
        "graph_relation",
        "DAC强调用户或所有者对对象权限的自主分配，但难以抵御特洛伊木马等滥用授权问题；MAC通过强制安全级别提供更强保护；RBAC以角色组织权限，能简化授权管理，但仍需要合理设计角色、约束和职责边界，资料也提示其相对于DAC和MAC既有优点也有不足。",
        [
            src("Word-5.docx", "访问控制技术 / DAC与MAC", "MAC可提供更强安全保护层，以防范偶然或故意滥用DAC。"),
            src("word-1.docx", "访问控制技术 / RBAC", "RBAC相对于DAC和MAC的优点和不足。"),
        ],
        ["DAC", "MAC", "RBAC", "访问控制", "特洛伊木马", "角色"],
        "hard",
        "text",
        ["DAC自主授权", "MAC强制保护", "RBAC角色", "防范滥用DAC", "角色设计不足"],
    ),
    q(
        "Q131",
        "根据包过滤模型图和状态包检查流程图，说明状态检测防火墙比传统包过滤多使用了哪些判断信息。",
        "multi_modal",
        "包过滤模型主要依据过滤规则判断数据包是否转发，并可审计、报警或丢弃。状态包检查流程在此基础上先判断数据包是否属于已存在连接，并在转发后更新对话表，同时还检测内容是否被策略集允许。因此状态检测比传统包过滤多使用连接状态、对话表和内容策略信息。",
        [
            src("图片-1.png", "图1 包过滤模型", "流程判断是否与过滤规则匹配，决定审计报警、转发、发送NACK或丢弃包。", "image"),
            src("图片-2.png", "图11 状态包检查的逻辑流程", "先判断数据包是否属于已经存在的连接，最终转发并更新对话表，进行日志记录。", "image"),
        ],
        ["包过滤", "状态包检查", "连接状态", "对话表", "过滤规则", "内容策略"],
        "hard",
        "mixed",
        ["过滤规则", "已存在连接", "内容检测", "策略集", "更新对话表"],
    ),
    q(
        "Q132",
        "状态包检查流程图中新连接数据包和已有连接数据包的处理路径有何不同？",
        "image_question",
        "新连接数据包先检测是否符合规则集，只有通过规则集检测后才进入内容策略判断；已有连接数据包可以直接进入特定内容检测和策略集判断。两类数据包最终若策略允许，则转发到目的地并更新对话表和记录日志；若不允许，则拒绝或丢弃并记录日志。",
        [src("图片-2.png", "图11 状态包检查的逻辑流程", "新连接路径检测规则集；已有连接路径进入内容检测；允许则转发并更新对话表，不允许则拒绝或丢弃并记录日志。", "image")],
        ["状态包检查", "新连接", "已有连接", "规则集", "对话表", "日志记录"],
        "medium",
        "image",
        ["新连接检测规则集", "已有连接进入内容检测", "策略允许", "转发", "更新对话表", "日志记录"],
    ),
    q(
        "Q133",
        "TCP连接过程图中，客户机和服务器的IP地址分别是什么？被防火墙阻止的是哪一类连接尝试？",
        "image_question",
        "图中客户机IP地址为202.202.42.136，服务器IP地址为202.202.41.142。序列图中有一条从服务器到客户机、标记ACK=1的连接尝试被叉号标出，并标注为企图连接、被防火墙阻止，表示防火墙阻断了不符合连接状态或策略的非法连接尝试。",
        [src("图片-3.png", "图2 TCP的连接过程", "客户机IP为202.202.42.136，服务器IP为202.202.41.142；标记ACK=1的企图连接被防火墙阻止。", "image")],
        ["TCP连接过程", "202.202.42.136", "202.202.41.142", "ACK", "防火墙阻止"],
        "medium",
        "image",
        ["客户机IP", "服务器IP", "ACK=1", "企图连接", "防火墙阻止"],
    ),
    q(
        "Q134",
        "远程访问VPN图中列出了VPN的哪五项功能？这些功能服务于什么场景？",
        "image_question",
        "图中列出的VPN功能包括访问控制管理、用户认证、数据加密、智能监控与审计日志、密钥和数字证书管理。这些功能服务于远程办公或移动用户通过Internet访问公司总部资源的场景。",
        [src("图片-4.png", "图16 远程访问VPN", "VPN功能包括Access Control Management、User Authentication、Data Encryption、Intelligent Monitoring and Audit Logs、Key and Digital Certificate Management。", "image")],
        ["远程访问VPN", "访问控制", "用户认证", "数据加密", "审计日志", "数字证书"],
        "easy",
        "image",
        ["访问控制管理", "用户认证", "数据加密", "智能监控与审计日志", "密钥和数字证书管理"],
    ),
    q(
        "Q135",
        "外联网VPN图中，总部LAN与子公司LAN之间的认证和加密关系是如何表示的？",
        "image_question",
        "图中总部LAN和子公司LAN分别通过VPN服务器、防火墙连接到Internet。两个VPN服务器之间有一条跨越Internet的VPN双向箭头，下方还有认证和加密箭头，表示两个站点之间的通信通过VPN隧道进行身份认证和数据加密。图中还提示VPN服务器访问控制应详细周到，且不能与防火墙和协议发生冲突。",
        [src("图片-5.png", "图17 外联网VPN", "总部LAN与子公司LAN通过两个VPN服务器和防火墙连接，VPN箭头跨越两端，下方标注认证和加密；访问控制应详细周到，不能与防火墙和协议冲突。", "image")],
        ["外联网VPN", "总部LAN", "子公司LAN", "认证", "加密", "访问控制"],
        "medium",
        "image",
        ["两个VPN服务器", "防火墙", "VPN双向箭头", "认证", "加密", "访问控制详细"],
    ),
    q(
        "Q136",
        "双宿主网关上的代理服务器图中，请求、答复和审计监控之间的关系是什么？",
        "image_question",
        "图中代理位于Internet和内部客户机之间，Internet客户和内部客户机都通过代理进行请求与答复交互。代理支持WWW、FTP、E-mail等服务，并向下连接审计、监控、报警和安全策略模块，说明代理不仅转发应用层请求，还承担安全审计和策略执行作用。",
        [src("图片-6.png", "图7 Internet客户通过代理服务器访问内部网主机", "双宿主网关上的代理连接Internet和客户机，请求与答复均经过代理，代理下方连接审计、监控、报警、安全策略。", "image")],
        ["双宿主网关", "代理服务器", "请求", "答复", "审计", "监控", "安全策略"],
        "medium",
        "image",
        ["Internet", "客户机", "代理", "请求答复", "审计监控报警", "安全策略"],
    ),
    q(
        "Q137",
        "课程资料是否详细介绍了OAuth 2.0授权码模式与OpenID Connect ID Token的验证流程？",
        "unanswerable",
        "课程资料没有提供OAuth 2.0授权码模式或OpenID Connect ID Token验证流程的系统性内容。回答应说明资料不足，不能补充资料外的协议细节。",
        [],
        ["OAuth 2.0", "OpenID Connect", "ID Token", "授权码模式"],
        "medium",
        "text",
        ["资料不足", "不应编造", "未介绍OAuth2", "未介绍OpenID Connect"],
        answerable=False,
        acceptable_sources=[],
    ),
    q(
        "Q138",
        "根据课程资料，请给出TLS 1.3中0-RTT早期数据的重放攻击风险和完整防御机制。",
        "unanswerable",
        "课程资料只涉及SSL/TLS的一般安全作用，没有详细介绍TLS 1.3、0-RTT早期数据或其重放攻击防御机制。回答应说明资料不足。",
        [],
        ["TLS 1.3", "0-RTT", "早期数据", "重放攻击"],
        "hard",
        "text",
        ["资料不足", "TLS 1.3未展开", "0-RTT未介绍", "不应补充外部知识"],
        answerable=False,
        acceptable_sources=[],
    ),
    q(
        "Q139",
        "课程资料是否给出了Kubernetes NetworkPolicy与Service Mesh安全策略的配置示例？",
        "unanswerable",
        "课程资料没有涉及Kubernetes NetworkPolicy或Service Mesh安全策略配置示例。回答应明确说明课程资料中未提供相关内容。",
        [],
        ["Kubernetes", "NetworkPolicy", "Service Mesh", "安全策略"],
        "medium",
        "text",
        ["资料不足", "未介绍Kubernetes", "未介绍Service Mesh", "无配置示例"],
        answerable=False,
        acceptable_sources=[],
    ),
    q(
        "Q140",
        "根据课程资料，请比较Passkey、FIDO2和WebAuthn在浏览器无密码登录中的协议细节。",
        "unanswerable",
        "课程资料没有提供Passkey、FIDO2或WebAuthn无密码登录协议细节。回答应说明资料不足，不能根据课程资料完成比较。",
        [],
        ["Passkey", "FIDO2", "WebAuthn", "无密码登录"],
        "medium",
        "text",
        ["资料不足", "未介绍Passkey", "未介绍FIDO2", "未介绍WebAuthn"],
        answerable=False,
        acceptable_sources=[],
    ),
]


def main():
    base_items = json.loads(SOURCE.read_text(encoding="utf-8"))
    if isinstance(base_items, dict):
        base_items = base_items.get("questions", [])
    items = [enrich(item) for item in base_items] + NEW_ITEMS

    ids = [item["question_id"] for item in items]
    if len(ids) != len(set(ids)):
        dup = sorted({x for x in ids if ids.count(x) > 1})
        raise SystemExit(f"duplicate ids: {dup}")

    DATASET_OUT.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    spec_questions = []
    for item in items:
        spec_questions.append(
            {
                "id": item["question_id"],
                "type": item["question_type"],
                "text": item["question"],
                "expected_source_names": _files_from_sources(item.get("golden_sources", [])),
                "expected_chunk_ids": [],
                "expected_doc_ids": [],
            }
        )
    SPEC_OUT.write_text(
        json.dumps({"questions": spec_questions}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {DATASET_OUT.relative_to(ROOT)} ({len(items)} questions)")
    print(f"wrote {SPEC_OUT.relative_to(ROOT)} ({len(spec_questions)} questions)")


if __name__ == "__main__":
    main()
