"""Article formulas: the built-in catalog of styles and the formulas an author saves under a name."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, col, select

from proseferno.api.deps import SessionDep
from proseferno.api.schemas import FormulaCatalogOut, FormulaIn, FormulaOut
from proseferno.db import Formula, utcnow
from proseferno.writer.formulas import AUTO, NOTE_FIELDS, PART_FIELDS, catalog, clean, formula_label, resolve_formula

router = APIRouter(prefix="/api")


def formula_out(row: Formula) -> FormulaOut:
    return FormulaOut(**row.model_dump(exclude={"updated_at"}), label=formula_label(resolve_formula(row.model_dump())))


def _formula_or_404(session: Session, formula_id: int) -> Formula:
    row = session.get(Formula, formula_id)
    if row is None:
        raise HTTPException(404, "Formula not found.")
    return row


def _apply(session: Session, row: Formula, body: FormulaIn) -> Formula:
    name = body.name.strip()
    clash = session.exec(select(Formula).where(col(Formula.name).ilike(name))).first()
    if clash is not None and clash.id != row.id:
        raise HTTPException(409, f"A formula named '{clash.name}' already exists.")
    parts = clean(body.model_dump())
    if not parts or (all(parts.get(f, AUTO) == AUTO for f in PART_FIELDS) and not any(parts.get(f) for f in NOTE_FIELDS)):
        raise HTTPException(422, "Choose at least one part of the formula or write your own instructions for one.")
    row.name = name
    row.description = body.description.strip()
    for field in PART_FIELDS:
        setattr(row, field, parts.get(field, AUTO))
    for field in NOTE_FIELDS:
        setattr(row, field, parts.get(field, ""))
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/formulas/catalog", response_model=FormulaCatalogOut)
def formula_catalog() -> FormulaCatalogOut:
    """Every article type, opener, body and closer style a formula can be built from."""
    return FormulaCatalogOut(**catalog())


@router.get("/formulas", response_model=list[FormulaOut])
def list_formulas(session: SessionDep) -> list[FormulaOut]:
    return [formula_out(row) for row in session.exec(select(Formula).order_by(col(Formula.name)))]


@router.post("/formulas", response_model=FormulaOut, status_code=201)
def create_formula(body: FormulaIn, session: SessionDep) -> FormulaOut:
    return formula_out(_apply(session, Formula(name=body.name), body))


@router.put("/formulas/{formula_id}", response_model=FormulaOut)
def update_formula(formula_id: int, body: FormulaIn, session: SessionDep) -> FormulaOut:
    return formula_out(_apply(session, _formula_or_404(session, formula_id), body))


@router.delete("/formulas/{formula_id}", status_code=204)
def delete_formula(formula_id: int, session: SessionDep) -> None:
    session.delete(_formula_or_404(session, formula_id))
    session.commit()
