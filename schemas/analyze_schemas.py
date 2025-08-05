from pydantic import BaseModel, HttpUrl

class AnalyzeUrlPdfInput(BaseModel):
    downloadUrl: HttpUrl
