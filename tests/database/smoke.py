"""Construct a synthetic model; never imply an ORM extractor produced it."""

from arctrellis.database import DatabaseAnalysisResult
from tests.database.test_foundation import observation


def main() -> None:
    value = observation()
    result = DatabaseAnalysisResult.from_observations((value,))
    print("Database operation model: available=yes")
    print("Providers modeled: " + ", ".join(provider for provider, _ in result.provider_counts))
    print("Observation graph conversion: deferred")
    print("Example origin: synthetic construction, no extractor")
    print(f"owner={value.owner_entity_id} kind={value.operation_kind.value} name={value.operation_name}")
    print(f"target={value.target_name} location={value.location.file_path}:{value.location.start_line}")
    print(f"id={value.id}")


if __name__ == "__main__":
    main()
