"""
Access service for handling collaborator access requests.
"""

import smtplib
from datetime import datetime
from email.mime.text import MIMEText

from loguru import logger

from ..models.requests import AccessRequestRequest
from ..models.responses import AccessRequestResult


class AccessService:
    """Service for handling access requests and email notifications."""

    def __init__(self):
        """Initialize the access service."""
        self.sender_email = "softpack@sanger.ac.uk"
        self.recipient_email = "hgi@sanger.ac.uk"
        self.smtp_server = "mail.internal.sanger.ac.uk"
        self.smtp_port = 25

    async def request_collaborator_access(self, request: AccessRequestRequest) -> AccessRequestResult:
        """
        Request collaborator access to spack-repo.

        This method sends an email to the HGI service desk requesting
        collaborator access for the specified GitHub username.

        Args:
            request: Access request parameters

        Returns:
            Access request result with status and details.
        """
        try:
            # Create email content
            subject = "Spack Repo Collaborator Access Request"
            body = self._create_access_request_email_body(request)

            # Send email
            email_sent = await self._send_email(subject, body)

            if email_sent:
                logger.info(
                    "Access request email sent successfully",
                    github_username=request.github_username,
                    package_name=request.package_name,
                    session_id=request.session_id,
                )

                return AccessRequestResult(
                    success=True,
                    message="Access request sent successfully to HGI Service Desk",
                    github_username=request.github_username,
                    package_name=request.package_name,
                    email_sent=True,
                    email_details={
                        "sent_at": datetime.now().isoformat(),
                        "recipient": self.recipient_email,
                        "subject": subject,
                    },
                )
            else:
                logger.error(
                    "Failed to send access request email",
                    github_username=request.github_username,
                    package_name=request.package_name,
                )

                return AccessRequestResult(
                    success=False,
                    message="Failed to send access request email. Please contact HGI Service Desk directly.",
                    github_username=request.github_username,
                    package_name=request.package_name,
                    email_sent=False,
                    email_details={"error": "SMTP connection failed"},
                )

        except Exception as e:
            logger.exception(
                "Error processing access request",
                github_username=request.github_username,
                package_name=request.package_name,
                error=str(e),
            )

            return AccessRequestResult(
                success=False,
                message=f"Failed to process access request: {str(e)}",
                github_username=request.github_username,
                package_name=request.package_name,
                email_sent=False,
                email_details={"error": str(e)},
            )

    def _create_access_request_email_body(self, request: AccessRequestRequest) -> str:
        """
        Create the email body for access request.

        Args:
            request: Access request parameters

        Returns:
            Formatted email body
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        body = f"""Hi HGI Service Desk,

A user has requested collaborator access to the spack-repo repository.

Request Details:
- GitHub Username: {request.github_username}
- Package Name: {request.package_name}
- Session ID: {request.session_id or 'N/A'}
- Request Time: {current_time}

This user is working on creating a Spack package recipe and needs collaborator access to create pull requests.

Please review this request and grant collaborator access to the spack-repo repository if appropriate.

Repository: https://github.com/wtsi-hgi/spack-repo

Best regards,
Softpack Team
"""
        return body

    async def _send_email(self, subject: str, body: str) -> bool:
        """
        Send email using SMTP.

        Args:
            subject: Email subject
            body: Email body

        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEText(body, "plain")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = self.recipient_email

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False


# Dependency injection
_access_service: AccessService | None = None


def get_access_service() -> AccessService:
    """Get the access service instance."""
    global _access_service
    if _access_service is None:
        _access_service = AccessService()
    return _access_service
