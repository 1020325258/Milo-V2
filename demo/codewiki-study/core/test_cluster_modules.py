"""模块名清洗函数的单元测试"""

import pytest
from core.cluster_modules import sanitize_module_name, sanitize_module_tree_keys


# ─────────────────────────────────────────────────────────────
# sanitize_module_name
# ─────────────────────────────────────────────────────────────

class TestSanitizeModuleName:
    """sanitize_module_name 的各种输入场景"""

    def test_spaces_to_underscores(self):
        assert sanitize_module_name("Contract PDF Generation") == "contract_pdf_generation"

    def test_hyphens_to_underscores(self):
        assert sanitize_module_name("Contract-Context-Handler") == "contract_context_handler"

    def test_mixed_separators(self):
        assert sanitize_module_name("Personal Relation & Signing") == "personal_relation_signing"

    def test_already_snake_case(self):
        assert sanitize_module_name("contract_context_handler") == "contract_context_handler"

    def test_leading_trailing_spaces(self):
        assert sanitize_module_name("  Contract PDF  ") == "contract_pdf"

    def test_special_characters_removed(self):
        assert sanitize_module_name("Contract (v2.0) & Review") == "contract_v20_review"

    def test_chinese_characters_preserved(self):
        assert sanitize_module_name("合同模块管理") == "合同模块管理"

    def test_chinese_with_english(self):
        assert sanitize_module_name("合同 PDF 生成") == "合同_pdf_生成"

    def test_consecutive_separators_merged(self):
        assert sanitize_module_name("Contract   PDF") == "contract_pdf"
        assert sanitize_module_name("Contract---PDF") == "contract_pdf"

    def test_only_special_characters(self):
        assert sanitize_module_name("& / ()") == ""

    def test_single_word(self):
        assert sanitize_module_name("Contract") == "contract"

    def test_leading_trailing_underscores_stripped(self):
        assert sanitize_module_name("_Contract_") == "contract"

    def test_dot_removed(self):
        assert sanitize_module_name("v2.0.Module") == "v20module"

    def test_slash_removed(self):
        assert sanitize_module_name("combo/material/pdf") == "combomaterialpdf"


# ─────────────────────────────────────────────────────────────
# sanitize_module_tree_keys
# ─────────────────────────────────────────────────────────────

class TestSanitizeModuleTreeKeys:
    """sanitize_module_tree_keys 对模块树的递归清洗"""

    def test_flat_tree(self):
        tree = {
            "Contract PDF Generation": {"components": ["a::b"]},
            "Personal Relation & Signing": {"components": ["c::d"]},
        }
        result = sanitize_module_tree_keys(tree)
        assert set(result.keys()) == {"contract_pdf_generation", "personal_relation_signing"}

    def test_nested_children(self):
        tree = {
            "Contract Context Management": {
                "components": [],
                "children": {
                    "Contract Context Handler": {"components": ["a::b"]},
                    "Contract Detail Context Handler": {"components": ["c::d"]},
                },
            },
        }
        result = sanitize_module_tree_keys(tree)
        assert "contract_context_management" in result
        children = result["contract_context_management"]["children"]
        assert set(children.keys()) == {"contract_context_handler", "contract_detail_context_handler"}

    def test_empty_tree(self):
        assert sanitize_module_tree_keys({}) == {}

    def test_no_children_key(self):
        tree = {"Contract Service": {"components": ["a::b"]}}
        result = sanitize_module_tree_keys(tree)
        assert "contract_service" in result
        assert result["contract_service"]["components"] == ["a::b"]

    def test_empty_children(self):
        tree = {
            "Contract Service": {
                "components": ["a::b"],
                "children": {},
            },
        }
        result = sanitize_module_tree_keys(tree)
        assert result["contract_service"]["children"] == {}


# ─────────────────────────────────────────────────────────────
# parse_cluster_response
# ─────────────────────────────────────────────────────────────

class TestParseClusterResponse:
    """parse_cluster_response 解析 + 清洗一体化"""

    def test_parse_with_spaces_in_keys(self):
        from core.cluster_modules import parse_cluster_response
        response = """Some reasoning...

<GROUPED_COMPONENTS>
{
    "Contract PDF Generation": {
        "path": "contract/pdf",
        "components": ["a::b"]
    },
    "Personal Relation & Signing": {
        "path": "personal",
        "components": ["c::d"]
    }
}
</GROUPED_COMPONENTS>"""
        result = parse_cluster_response(response)
        assert result is not None
        assert set(result.keys()) == {"contract_pdf_generation", "personal_relation_signing"}

    def test_parse_with_snake_case_keys(self):
        from core.cluster_modules import parse_cluster_response
        response = """<GROUPED_COMPONENTS>
{
    "contract_context_handler": {
        "path": "context",
        "components": ["a::b"]
    }
}
</GROUPED_COMPONENTS>"""
        result = parse_cluster_response(response)
        assert result is not None
        assert "contract_context_handler" in result

    def test_parse_missing_tags(self):
        from core.cluster_modules import parse_cluster_response
        assert parse_cluster_response("no tags here") is None

    def test_parse_invalid_json(self):
        from core.cluster_modules import parse_cluster_response
        assert parse_cluster_response("<GROUPED_COMPONENTS>not json</GROUPED_COMPONENTS>") is None
