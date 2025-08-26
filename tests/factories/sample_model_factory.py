"""
SampleModel 테스트 데이터 팩토리
"""

from tests.conftest import SampleModel


class SampleModelFactory:
    """Factory class for creating SampleModel test data"""

    @classmethod
    def create_basic_model(cls, name: str = "Default Name", **kwargs) -> SampleModel:
        """Create a basic SampleModel with default name"""
        data = {"name": name}
        data.update(kwargs)
        return SampleModel(**data)

    @classmethod
    def create_test_model(cls, suffix: str = "01", **kwargs) -> SampleModel:
        """Create a SampleModel for general testing purposes"""
        data = {"name": f"Test Model {suffix}"}
        data.update(kwargs)
        return SampleModel(**data)

    @classmethod
    def create_save_test_model(cls, **kwargs) -> SampleModel:
        """Create a SampleModel specifically for save operation testing"""
        data = {"name": "Save Test"}
        data.update(kwargs)
        return SampleModel(**data)

    @classmethod
    def create_existence_test_model(cls, **kwargs) -> SampleModel:
        """Create a SampleModel for testing existence checks"""
        data = {"name": "Existence Test"}
        data.update(kwargs)
        return SampleModel(**data)
