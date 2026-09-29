from pydantic import BaseModel, Field

from app.models.cargo import CargoStatus, DocType


class ShipmentCreate(BaseModel):
    expedition_id: str
    origin: str = "Goa"
    destination: str = "Bharati"


class ShipmentResponse(BaseModel):
    id: str
    expedition_id: str
    origin: str
    destination: str
    status: CargoStatus
    current_location: str

    model_config = {"from_attributes": True}


class StatusUpdate(BaseModel):
    to_status: CargoStatus
    reason: str = ""
    location: str | None = None


class ContainerCreate(BaseModel):
    code: str | None = None


class ContainerResponse(BaseModel):
    id: str
    shipment_id: str
    code: str
    location: str

    model_config = {"from_attributes": True}


class PackageCreate(BaseModel):
    description: str = ""
    weight_kg: float = 0.0


class PackageResponse(BaseModel):
    id: str
    container_id: str
    shipment_id: str
    description: str
    weight_kg: float
    status: CargoStatus
    location: str
    qr_code: str = Field(description="base64 PNG QR encoding the package id")

    model_config = {"from_attributes": True}


class ItemCreate(BaseModel):
    name: str
    quantity: float = 1.0
    unit: str = "pcs"
    category: str = "Scientific supplies"


class ItemResponse(BaseModel):
    id: str
    package_id: str
    name: str
    quantity: float
    unit: str
    category: str

    model_config = {"from_attributes": True}


class DocumentGenerate(BaseModel):
    doc_type: DocType


class DocumentResponse(BaseModel):
    id: str
    shipment_id: str
    package_id: str | None
    doc_type: DocType
    status: str
    pdf_path: str

    model_config = {"from_attributes": True}


class ScanRequest(BaseModel):
    package_id: str = Field(description="BX-… id or raw QR payload POLARIS:<id>")
    to_status: CargoStatus | None = None
    location: str | None = None


class ScanResponse(BaseModel):
    package: PackageResponse
    previous_status: str
    detail: str
