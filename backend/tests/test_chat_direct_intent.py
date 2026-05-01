from app.services.chat_service import _classify_direct_intent


def test_direct_intent_detects_document_count_questions():
    assert _classify_direct_intent("你现在库里有几个文档") == "kb_status"
    assert _classify_direct_intent("当前知识库有多少资料？") == "kb_status"

