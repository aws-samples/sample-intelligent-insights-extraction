import json
import logging
import time
import os
import boto3
from fastmcp.server.auth import  AccessToken, TokenVerifier

# Configure logging with more detailed format
token_logger = logging.getLogger("mcp_token")
token_logger.setLevel(logging.DEBUG)

# Add handler if not already present
if not token_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    handler.setFormatter(formatter)
    token_logger.addHandler(handler)

# Set boto3 and AWS SDK loggers to ERROR level to reduce noise
logging.getLogger('boto3').setLevel(logging.ERROR)
logging.getLogger('botocore').setLevel(logging.ERROR)
logging.getLogger('s3transfer').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

class SecretManagerTokenVerifier(TokenVerifier):
    """
    Token verifier that retrieves a single API key from AWS Secrets Manager with strict rotation schedule.

    This verifier fetches an API key from AWS Secrets Manager and caches it until
    the next rotation date. It strictly follows the rotation schedule without
    arbitrary cache expiration.

    Expected secret format:
    {
        "api-key": "your-secret-api-key-here",
        "rotation_date": "2025-08-30T00:00:00Z"  // required ISO format
    }
    """

    def __init__(
            self,
            required_scopes: list[str] | None = None,
    ):
        """
        Initialize the Secrets Manager token verifier.

        Args:
            required_scopes: Required scopes for all tokens
        """
        token_logger.info("Initializing SecretManagerTokenVerifier")
        super().__init__(required_scopes=required_scopes)
        self.token = None
        self.next_rotation_date = None
        self._refresh_token()
        token_logger.info(f"Initialization complete - Token loaded: {bool(self.token)}")

    def _refresh_token(self):
        """Refresh the token from Secrets Manager."""
        token_logger.info("Refreshing token from Secrets Manager")
        secret_data = self.get_secret_from_secrets_manager()
        
        if secret_data:
            self.token = secret_data.get("api-key")
            token_logger.info(f"Token retrieved successfully")

            # Get rotation information from describe_secret API
            self.next_rotation_date = self.get_next_rotation_date()
            
            if self.next_rotation_date:
                # Use explicit UTC time for consistency in Fargate
                import datetime
                utc_now = datetime.datetime.now(datetime.timezone.utc)
                current_time = utc_now.timestamp()
                
                # Ensure both values are timestamps (floats) for calculation
                if isinstance(self.next_rotation_date, (int, float)):
                    time_until_rotation = self.next_rotation_date - current_time
                    rotation_datetime = datetime.datetime.fromtimestamp(self.next_rotation_date, tz=datetime.timezone.utc)
                    token_logger.info(f"Next rotation: {rotation_datetime.strftime('%Y-%m-%d %H:%M UTC')} ({time_until_rotation/3600:.1f}h)")
                else:
                    token_logger.warning(f"Unexpected type for next_rotation_date: {type(self.next_rotation_date)}")
            else:
                token_logger.warning("No rotation schedule found - token will not be cached")
        else:
            token_logger.error("Failed to retrieve secret data")
            self.token = None
            self.next_rotation_date = None

    def get_next_rotation_date(self) -> float | None:
        """Get the next rotation date from AWS Secrets Manager rotation configuration."""
        secret_name = os.environ.get("API_SECRET_NAME")
        region = os.environ.get("AWS_REGION", "us-east-1")
        
        if not secret_name:
            token_logger.warning("API_SECRET_NAME not set, cannot get rotation info")
            return None
            
        try:
            token_logger.debug("Getting rotation schedule from describe_secret API")
            session = boto3.session.Session()
            client = session.client(
                service_name="secretsmanager",
                region_name=region,
            )
            
            # Use describe_secret to get rotation configuration
            response = client.describe_secret(SecretId=secret_name)
            token_logger.debug(f"Describe secret response keys: {list(response.keys())}")
            
            # Check if rotation is enabled
            rotation_enabled = response.get('RotationEnabled', False)
            token_logger.info(f"Rotation enabled: {rotation_enabled}")
            
            if not rotation_enabled:
                token_logger.info("Automatic rotation is not enabled for this secret")
                return None
            
            # Get NextRotationDate directly from the response
            next_rotation_date = response.get('NextRotationDate')
            if next_rotation_date:
                # Convert datetime to timestamp if needed
                if hasattr(next_rotation_date, 'timestamp'):
                    next_rotation_timestamp = next_rotation_date.timestamp()
                else:
                    # Already a timestamp
                    next_rotation_timestamp = float(next_rotation_date)
                    
                token_logger.info(f"Next scheduled rotation: {next_rotation_date} (timestamp: {next_rotation_timestamp})")
                
                # Log rotation rules for information
                rotation_rules = response.get('RotationRules', {})
                if rotation_rules:
                    automatically_after_days = rotation_rules.get('AutomaticallyAfterDays')
                    token_logger.info(f"Rotation interval: {automatically_after_days} days")
                
                return next_rotation_timestamp
            else:
                token_logger.warning("NextRotationDate not found in response")
                return None
                
        except Exception as e:
            token_logger.error(f"Error getting rotation schedule: {str(e)}")
            token_logger.debug(f"Exception details: {type(e).__name__}: {e}")
            return None

    def _should_refresh_token(self) -> bool:
        """Check if token should be refreshed based on rotation date."""
        if not self.token:
            token_logger.info("Token refresh needed: No token available")
            return True

        if not self.next_rotation_date:
            token_logger.debug("Token refresh needed: No rotation date set")
            return True

        # Use explicit UTC time to avoid timezone issues in Fargate
        import datetime
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        current_time = utc_now.timestamp()

        # Refresh only if we've passed the rotation date
        if current_time >= self.next_rotation_date:
            token_logger.info("Token refresh needed: Rotation date reached")
            return True

        return False

    def get_secret_from_secrets_manager(self) -> dict | None:
        """Retrieve the complete secret data from AWS Secrets Manager."""
        secret_name = os.environ.get("API_SECRET_NAME")
        region = os.environ.get("AWS_REGION", "us-east-1")
        
        token_logger.info(f"Retrieving secret '{secret_name}' from region '{region}'")
        
        if not secret_name:
            token_logger.critical("API_SECRET_NAME environment variable not set")
            return None

        try:
            token_logger.debug("Creating boto3 session and secrets manager client")
            session = boto3.session.Session()
            client = session.client(
                service_name="secretsmanager",
                region_name=region,
            )
            
            token_logger.debug(f"Calling get_secret_value for secret: {secret_name}")
            response = client.get_secret_value(SecretId=secret_name)
            
            token_logger.debug(f"Received response with keys: {list(response.keys())}")
            secret_data = json.loads(response["SecretString"])
            token_logger.debug(f"Parsed secret data with keys: {list(secret_data.keys())}")

            # Validate required fields
            api_key = secret_data.get("api-key")
            if not api_key:
                token_logger.critical("No 'api-key' field found in the secret")
                return None

            token_logger.info(f"Successfully retrieved secret. API key length: {len(api_key)}")
            return secret_data
            
        except Exception as e:
            token_logger.critical(f"Error retrieving secret from Secrets Manager: {str(e)}")
            token_logger.debug(f"Exception details: {type(e).__name__}: {e}")
            return None

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify token against the API key from Secrets Manager with strict rotation schedule."""
        token_logger.debug(f"Token verification request - length: {len(token) if token else 0}")

        # Check if we need to refresh the token based on rotation date
        if self._should_refresh_token():
            token_logger.info("Refreshing token due to rotation schedule")
            self._refresh_token()

        if not self.token:
            token_logger.warning("No API key available for verification")
            return None

        # Check if the provided token matches our API key
        if token != self.token:
            token_logger.warning("Token verification failed: Invalid token")
            return None

        token_logger.info("Token verification successful")
        
        # Check required scopes
        provided_scopes = ["read:data"]
        if self.required_scopes:
            token_scopes = set(provided_scopes)
            required_scopes = set(self.required_scopes)
            if not required_scopes.issubset(token_scopes):
                token_logger.error(f"Scope mismatch - required: {required_scopes}, provided: {token_scopes}")
                return None

        # Token is valid, create AccessToken with 10-minute expiration
        import datetime
        
        # Get current UTC time explicitly
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        current_time = int(utc_now.timestamp())
        token_expires_at = current_time + (10 * 60)  # 10 minutes from now
        
        # Create expiration datetime from the same timestamp for consistency
        expires_datetime = datetime.datetime.fromtimestamp(token_expires_at, tz=datetime.timezone.utc)
        
        token_logger.info(f"Creating AccessToken - expires: {expires_datetime.strftime('%H:%M:%S UTC')}")

        access_token = AccessToken(
            token=token,
            client_id="mcp_client_token",
            scopes=["read:data"],
            expires_at=token_expires_at,
            resource=None,
        )
        
        token_logger.info(f"AccessToken created successfully for client: {access_token.client_id}")
        return access_token