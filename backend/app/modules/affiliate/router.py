"""Own APIRouter (Product/Link CRUD, score recompute) -- self-contained
within this module, per app/modules/README.md. The AI-powered
recommend-categories/recommend-products endpoints deliberately live
outside this file, in the composition root
app/api/v1/endpoints/affiliate_recommend.py (this module must never
import app.modules.ai).

`redirect_router` is a SEPARATE APIRouter, mounted directly on the FastAPI
`app` (see main.py) with no /api/v1 prefix, for a short, shareable public
link shape (/r/{code}). Real click counting only works once wherever a
link is posted can actually reach this backend -- for the default
desktop-local deployment (127.0.0.1, no public domain), that's only true
from the same machine. Same category of constraint as Task 11's TikTok
OAuth redirect_uri: this module builds the real, correct mechanism, but
making it reachable from an actual social-media click requires the user
to expose this backend publicly (reverse proxy/tunnel) -- not something
this app can do on its own. See docs/features/77-affiliate-engine.md.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_db
from app.modules.affiliate.schemas import LinkCreateIn, LinkOut, ProductCreateIn, ProductOut, ProductUpdateIn
from app.modules.affiliate.service import LinkService, ProductService

router = APIRouter()
redirect_router = APIRouter()


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    return ProductService(db)


def get_link_service(db: Session = Depends(get_db)) -> LinkService:
    return LinkService(db)


# -- Products -------------------------------------------------------------


@router.get("/affiliate/products", response_model=list[ProductOut])
def list_products(category: str | None = None, active_only: bool = False, service: ProductService = Depends(get_product_service)):
    return service.list_products(category, active_only)


@router.post("/affiliate/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreateIn, service: ProductService = Depends(get_product_service)):
    try:
        return service.create_product(**payload.model_dump())
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/affiliate/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, service: ProductService = Depends(get_product_service)):
    try:
        return service.get_product(product_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/affiliate/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductUpdateIn, service: ProductService = Depends(get_product_service)):
    try:
        return service.update_product(product_id, **payload.model_dump(exclude_unset=True))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/affiliate/products/{product_id}", status_code=204)
def delete_product(product_id: int, service: ProductService = Depends(get_product_service)):
    try:
        service.delete_product(product_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/affiliate/products/{product_id}/recompute-score", response_model=ProductOut)
def recompute_score(product_id: int, service: ProductService = Depends(get_product_service)):
    try:
        return service.recompute_score(product_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# -- Links ------------------------------------------------------------------


@router.get("/affiliate/products/{product_id}/links", response_model=list[LinkOut])
def list_links(product_id: int, service: LinkService = Depends(get_link_service)):
    return service.list_for_product(product_id)


@router.post("/affiliate/products/{product_id}/links", response_model=LinkOut, status_code=201)
def create_link(product_id: int, payload: LinkCreateIn, service: LinkService = Depends(get_link_service)):
    try:
        return service.create_link(product_id, payload.label)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/affiliate/links/{link_id}", status_code=204)
def delete_link(link_id: int, service: LinkService = Depends(get_link_service)):
    try:
        service.delete_link(link_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# -- Real click redirect ----------------------------------------------------


@redirect_router.get("/r/{link_code}")
def redirect_click(link_code: str, db: Session = Depends(get_db)):
    link = LinkService(db).record_click(link_code)
    if link is None:
        raise HTTPException(status_code=404, detail="Link không tồn tại.")
    return RedirectResponse(url=link.product.affiliate_url, status_code=302)
