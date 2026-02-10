from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TargetUsers(BaseModel):
    mainConsumers: Optional[str] = None
    applicationScenarios: Optional[str] = None

class BasicProductInfo(BaseModel):
    coreFunctions: Optional[str] = None
    materialsSpecs: Optional[str] = None
    imagesDescriptions: Optional[str] = None

class ProductDependencies(BaseModel):
    independentUsage: Optional[bool] = None
    essentialAccessories: Optional[List[str]] = Field(default_factory=list)
    recommendedComplements: Optional[List[str]] = Field(default_factory=list)
    relatedPrompts: Optional[str] = None

class PricingInfo(BaseModel):
    price: Optional[str] = None
    salesVolume: Optional[str] = None
    competitionSection: Optional[str] = None
    priceDifferentiators: Optional[List[str]] = Field(default_factory=list)

class ProductInnovation(BaseModel):
    innovations: Optional[str] = None
    differentiation: Optional[str] = None
    patentOrExclusive: Optional[str] = None

class DurabilityInfo(BaseModel):
    durability: Optional[str] = None
    environmentalInfo: Optional[str] = None

class UserFeedbackInfo(BaseModel):
    userConcerns: Optional[str] = None
    commonIssues: Optional[str] = None
    positiveHighlights: Optional[str] = None

class MarketInfo(BaseModel):
    opportunities: Optional[str] = None
    risks: Optional[str] = None

class SupplyChainInfo(BaseModel):
    inventory: Optional[str] = None
    supplyStability: Optional[str] = None

class Design(BaseModel):
    id: str
    title: str
    description: str
    imageUrl: str
    tags: List[str]
    s3Path: str
    industryFigures: Optional[List[str]] = Field(default_factory=list)
    source: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    contentType: Optional[str] = None
    publicationDate: Optional[str] = None
    technicalFocus: Optional[str] = None
    applicationAreas: Optional[str] = None
    mainContentHTML: Optional[str] = None
    targetUsers: Optional[TargetUsers] = None
    basicProductInfo: Optional[BasicProductInfo] = None
    productDependencies: Optional[ProductDependencies] = None
    pricingInfo: Optional[PricingInfo] = None
    productInnovation: Optional[ProductInnovation] = None
    durabilityInfo: Optional[DurabilityInfo] = None
    marketInfo: Optional[MarketInfo] = None
    supplyChainInfo: Optional[SupplyChainInfo] = None
    userFeedbackInfo: Optional[UserFeedbackInfo] = None

class DesignDetail(Design):
    relatedImages: Optional[List[str]] = Field(default_factory=list)
    originalUrl: Optional[str] = None
    timeUpdated: Optional[str] = None

class DesignSearchParams(BaseModel):
    tag: Optional[str] = None
    limit: int = 20
    page: int = 1
