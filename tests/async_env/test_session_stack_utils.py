# import pytest
#
# from transactional_sqlalchemy.utils.transaction_util import (
#     add_session_to_context, get_current_transaction_depth, get_session_stack_size, has_active_transaction,
#     remove_session_from_context,
# )
#
# @pytest.mark.no_autouse_fixtures
# class TestSessionStackUtils:
#     """세션 스택 유틸리티 함수 테스트"""
#
#     async def test_session_stack_operations(self, scoped_session_):
#         """세션 스택 기본 연산 테스트"""
#         # 초기 상태
#         assert get_session_stack_size() == 0
#         assert not has_active_transaction()
#
#         # 세션 추가
#         session = scoped_session_()
#         add_session_to_context(session)
#
#         assert get_session_stack_size() == 1
#         assert has_active_transaction()
#         assert get_current_transaction_depth() == 1
#
#         # 세션 제거
#         remove_session_from_context()
#
#         assert get_session_stack_size() == 0
#         assert not has_active_transaction()
#
#     async def test_multiple_session_stack(self, scoped_session_):
#         """다중 세션 스택 테스트"""
#         session1 = scoped_session_()
#         session2 = scoped_session_()
#
#         # 첫 번째 세션 추가
#         add_session_to_context(session1)
#         assert get_session_stack_size() == 1
#
#         # 두 번째 세션 추가
#         add_session_to_context(session2)
#         assert get_session_stack_size() == 2
#         assert get_current_transaction_depth() == 2
#
#         # LIFO 순서로 제거
#         remove_session_from_context()
#         assert get_session_stack_size() == 1
#
#         remove_session_from_context()
#         assert get_session_stack_size() == 0
