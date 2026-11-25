"""Column mapping service.

Stores a mapping per dataset: source column → target field, with required targets
(SKU, branch, quantity, price, date). Rejects incomplete mappings and duplicate
targets. Supports saving mappings as reusable templates.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.column_mapping import ColumnMapping
from app.schemas.column_mapping import ColumnMappingCreate, ColumnMappingUpdate


# Required target fields for each dataset type
REQUIRED_TARGETS: dict[str, list[str]] = {
    "sales": ["sku", "branch", "quantity", "price", "date"],
    "inventory": ["sku", "branch", "quantity_on_hand", "reorder_level", "date"],
}


def get_required_targets(dataset_type: str) -> list[str]:
    """Return the required target fields for a given dataset type."""
    return REQUIRED_TARGETS.get(dataset_type.lower(), [])


def validate_required_targets_complete(
    db: Session,
    dataset_type: str,
) -> dict:
    """Check if all required targets are covered for a dataset type.

    Returns a dict with:
    - complete: bool
    - missing_targets: list[str]
    - covered_targets: list[str]
    """
    dataset_type = dataset_type.lower()
    required = get_required_targets(dataset_type)

    if not required:
        return {
            "complete": False,
            "missing_targets": [],
            "covered_targets": [],
            "error": f"Unknown dataset type '{dataset_type}'",
        }

    existing = (
        db.query(ColumnMapping)
        .filter(ColumnMapping.dataset_type == dataset_type)
        .all()
    )
    covered = {m.target_field.lower() for m in existing}
    missing = [t for t in required if t not in covered]

    return {
        "complete": len(missing) == 0,
        "missing_targets": missing,
        "covered_targets": sorted(list(covered)),
    }


def create_column_mapping(
    db: Session,
    mapping_in: ColumnMappingCreate,
    created_by: UUID,
) -> ColumnMapping:
    """Create a new column mapping.

    Validates:
    - Dataset type has required targets defined
    - No duplicate source_column or target_field for the dataset
    """
    dataset_type = mapping_in.dataset_type.lower()
    required = get_required_targets(dataset_type)

    if not required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown dataset type '{mapping_in.dataset_type}'",
        )

    # Check for duplicate source_column
    existing_source = (
        db.query(ColumnMapping)
        .filter(
            ColumnMapping.dataset_type == dataset_type,
            ColumnMapping.source_column == mapping_in.source_column,
        )
        .first()
    )
    if existing_source:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source column '{mapping_in.source_column}' already mapped",
        )

    # Check for duplicate target_field
    existing_target = (
        db.query(ColumnMapping)
        .filter(
            ColumnMapping.dataset_type == dataset_type,
            ColumnMapping.target_field == mapping_in.target_field,
        )
        .first()
    )
    if existing_target:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Target field '{mapping_in.target_field}' already mapped",
        )

    mapping = ColumnMapping(
        dataset_type=dataset_type,
        source_column=mapping_in.source_column,
        target_field=mapping_in.target_field,
        is_template=mapping_in.is_template,
        created_by=created_by,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def get_column_mapping(
    db: Session,
    mapping_id: UUID,
) -> Optional[ColumnMapping]:
    """Get a column mapping by ID."""
    return db.query(ColumnMapping).filter(ColumnMapping.id == mapping_id).first()


def get_column_mappings(
    db: Session,
    dataset_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[ColumnMapping], int]:
    """List column mappings, optionally filtered by dataset type."""
    query = db.query(ColumnMapping)

    if dataset_type:
        query = query.filter(ColumnMapping.dataset_type == dataset_type.lower())

    total = query.count()
    items = (
        query.order_by(ColumnMapping.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def update_column_mapping(
    db: Session,
    mapping: ColumnMapping,
    mapping_in: ColumnMappingUpdate,
) -> ColumnMapping:
    """Update an existing column mapping."""
    update_data = mapping_in.model_dump(exclude_unset=True)

    if "source_column" in update_data:
        existing = (
            db.query(ColumnMapping)
            .filter(
                ColumnMapping.dataset_type == mapping.dataset_type,
                ColumnMapping.source_column == update_data["source_column"],
                ColumnMapping.id != mapping.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Source column '{update_data['source_column']}' already mapped",
            )

    if "target_field" in update_data:
        existing = (
            db.query(ColumnMapping)
            .filter(
                ColumnMapping.dataset_type == mapping.dataset_type,
                ColumnMapping.target_field == update_data["target_field"],
                ColumnMapping.id != mapping.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Target field '{update_data['target_field']}' already mapped",
            )

    for field, value in update_data.items():
        setattr(mapping, field, value)

    db.commit()
    db.refresh(mapping)
    return mapping


def delete_column_mapping(
    db: Session,
    mapping: ColumnMapping,
) -> None:
    """Delete a column mapping."""
    db.delete(mapping)
    db.commit()