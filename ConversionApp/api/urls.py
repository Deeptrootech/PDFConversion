from django.urls import path

from .views import ConvertAndMergeView

app_name = "conversion_api"


urlpatterns = [
    path("generate-merged-pdf/", ConvertAndMergeView.as_view(), name="download-pdf"),
    # path("upload-file/", UploadFile.as_view(), name="upload-file"),
]
