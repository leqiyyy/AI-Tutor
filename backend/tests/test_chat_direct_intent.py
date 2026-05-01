from app.services.chat_service import _classify_direct_intent
from app.services.question_router import route_question


def test_direct_intent_detects_document_count_questions():
    assert _classify_direct_intent("你现在库里有几个文档") == "kb_status"
    assert _classify_direct_intent("当前知识库有多少资料？") == "kb_status"


def test_direct_intent_detects_user_profile_question():
    assert _classify_direct_intent("我叫什么？") == "user_profile"


def test_router_respects_quick_llm_mode():
    route = route_question(question="快速解释一下 TCP 慢启动", role="student", answer_mode="quick_llm")
    assert route.route == "quick_llm"
    assert route.needs_retrieval is False
    assert route.forced_by_mode is True


def test_router_keeps_course_questions_on_rag_by_default():
    route = route_question(question="请结合资料解释 TCP 拥塞控制", role="student", answer_mode="auto")
    assert route.route == "course_rag"
    assert route.needs_retrieval is True


def test_router_detects_teacher_tool_for_teacher():
    route = route_question(question="帮我生成一份关于 TCP 的教案", role="teacher", answer_mode="auto")
    assert route.route == "teacher_tool"
    assert route.intent == "lesson_plan"


def test_router_strict_course_overrides_auto_teacher_tool_detection():
    route = route_question(question="帮我生成一份关于 TCP 的教案", role="teacher", answer_mode="strict_course")
    assert route.route == "course_rag"
    assert route.needs_retrieval is True
