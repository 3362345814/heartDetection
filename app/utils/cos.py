import uuid

from qcloud_cos import CosConfig, CosS3Client, CosServiceError

from app.core.config import settings

config = CosConfig(
    Region=settings.COS_REGION,
    SecretId=settings.COS_SECRET_ID,
    SecretKey=settings.COS_SECRET_KEY,
    Token=None,
    Scheme='https'
)

client = CosS3Client(config)


def upload_file_to_cos(file_stream, filename: str, content_type: str = "image/jpeg", path_prefix: str = None) -> str:
    if content_type == "image/jpeg":
        key = f"{path_prefix}/{uuid.uuid4().hex}.{filename.split('.')[-1]}"
    else:
        key = f"{path_prefix}/{filename}"
    response = client.put_object(
        Bucket=settings.COS_BUCKET_NAME,
        Body=file_stream,
        Key=key,
        ContentType=content_type
    )
    return f"https://{settings.COS_BUCKET_NAME}.cos.{settings.COS_REGION}.myqcloud.com/{key}"


def delete_file_from_cos(url: str):
    try:
        key = url.split(".myqcloud.com/")[-1]
        client.delete_object(Bucket=settings.COS_BUCKET_NAME, Key=key)
    except CosServiceError as e:
        print("Delete COS object failed:", e)
