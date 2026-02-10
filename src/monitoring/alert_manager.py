"""
Alert Manager

Sends alerts via SMS and email for:
- Execution summaries
- Error notifications
- Position changes
- System health issues
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Multi-channel alert system.
    
    Channels:
    - SMS via Twilio
    - Email via SMTP
    - Console logging (always on)
    """
    
    def __init__(self, config: Dict):
        """
        Initialize alert manager.
        
        Args:
            config: Alert configuration
        """
        self.config = config
        
        # SMS configuration
        self.sms_enabled = config.get("sms", {}).get("enabled", False)
        self.twilio_client = None
        
        if self.sms_enabled:
            try:
                from twilio.rest import Client as TwilioClient
                self.twilio_client = TwilioClient(
                    config["sms"]["account_sid"],
                    config["sms"]["auth_token"]
                )
                self.sms_from = config["sms"]["from_number"]
                self.sms_to = config["sms"]["to_number"]
            except ImportError:
                logger.warning("Twilio not installed, SMS alerts disabled")
                self.sms_enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize Twilio: {e}")
                self.sms_enabled = False
        
        # Email configuration
        self.email_enabled = config.get("email", {}).get("enabled", False)
        if self.email_enabled:
            self.smtp_config = config["email"]
    
    def send_execution_summary(self, results: Dict) -> None:
        """
        Send execution summary alert.
        
        Args:
            results: Execution results dictionary
        """
        positions = results.get("signals", {})
        
        message = (
            f"Trading Execution Complete\n"
            f"{'='*30}\n"
            f"Status: {results.get('status', 'unknown')}\n"
            f"Time: {results.get('timestamp', 'N/A')}\n"
            f"Mode: {'PAPER' if results.get('paper_mode') else 'LIVE'}\n\n"
            f"Target Positions:\n"
            f"  TQQQ: {positions.get('tqqq_target', 0):.1%}\n"
            f"  SQQQ: {positions.get('sqqq_target', 0):.1%}\n"
        )
        
        # Add account details
        accounts = results.get("accounts", {})
        for acc_id, acc_data in accounts.items():
            message += f"\nAccount {acc_id}:\n"
            message += f"  Portfolio: ${acc_data.get('portfolio_value', 0):,.2f}\n"
            
            orders = acc_data.get("executed_orders", [])
            if orders:
                message += "  Orders:\n"
                for order in orders:
                    message += f"    - {order.get('side', 'N/A')} {order.get('qty', 0)} {order.get('symbol', 'N/A')}\n"
        
        self._send_alert("Execution Summary", message, priority="normal")
    
    def send_error_alert(self, error: str, context: Optional[Dict] = None) -> None:
        """
        Send error alert.
        
        Args:
            error: Error message
            context: Optional context dictionary
        """
        message = f"TRADING ERROR\n{'='*30}\n\n{error}"
        
        if context:
            message += f"\n\nContext:\n"
            for key, value in context.items():
                message += f"  {key}: {value}\n"
        
        self._send_alert("Trading Error", message, priority="high")
    
    def send_position_change(self, old_positions: Dict, new_positions: Dict) -> None:
        """Send alert when positions change."""
        message = (
            f"Position Change\n"
            f"{'='*30}\n"
            f"TQQQ: {old_positions.get('TQQQ', 0):.1%} -> {new_positions.get('TQQQ', 0):.1%}\n"
            f"SQQQ: {old_positions.get('SQQQ', 0):.1%} -> {new_positions.get('SQQQ', 0):.1%}"
        )
        self._send_alert("Position Change", message, priority="normal")
    
    def send_system_status(self, status: Dict) -> None:
        """Send system status alert."""
        message = (
            f"System Status\n"
            f"{'='*30}\n"
            f"Initialized: {status.get('initialized', False)}\n"
            f"Paper Mode: {status.get('paper_mode', True)}\n"
            f"Data Loaded: {status.get('data_loaded', False)}\n"
            f"Connected Brokers: {', '.join(status.get('connected_brokers', []))}\n"
        )
        self._send_alert("System Status", message, priority="low")
    
    def send_daily_summary(self, portfolio_value: float, daily_return: float, positions: Dict) -> None:
        """Send daily performance summary."""
        message = (
            f"Daily Summary\n"
            f"{'='*30}\n"
            f"Portfolio Value: ${portfolio_value:,.2f}\n"
            f"Daily Return: {daily_return:+.2%}\n\n"
            f"Positions:\n"
        )
        
        for symbol, pos in positions.items():
            shares = pos.get("shares", 0)
            value = pos.get("market_value", 0)
            pl = pos.get("unrealized_pl", 0)
            message += f"  {symbol}: {shares:.2f} shares (${value:,.2f}, P/L: ${pl:+,.2f})\n"
        
        self._send_alert("Daily Summary", message, priority="normal")
    
    def _send_alert(self, subject: str, message: str, priority: str = "normal") -> None:
        """
        Send alert through all enabled channels.
        
        Args:
            subject: Alert subject
            message: Alert message
            priority: "low", "normal", or "high"
        """
        # Always log
        if priority == "high":
            logger.warning(f"ALERT [{subject}]: {message}")
        else:
            logger.info(f"ALERT [{subject}]: {message}")
        
        # Send SMS for high priority
        if self.sms_enabled and priority == "high":
            self._send_sms(f"{subject}\n\n{message}")
        
        # Send email for normal and high priority
        if self.email_enabled and priority in ["normal", "high"]:
            self._send_email(subject, message)
    
    def _send_sms(self, message: str) -> bool:
        """Send SMS via Twilio."""
        if not self.twilio_client:
            return False
        
        try:
            # Truncate message for SMS
            if len(message) > 1500:
                message = message[:1497] + "..."
            
            self.twilio_client.messages.create(
                body=message,
                from_=self.sms_from,
                to=self.sms_to
            )
            logger.info("SMS sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False
    
    def _send_email(self, subject: str, message: str) -> bool:
        """Send email via SMTP."""
        if not self.email_enabled:
            return False
        
        try:
            # Handle multiple recipients (comma-separated)
            to_addresses = self.smtp_config["to_address"]
            if isinstance(to_addresses, str):
                to_addresses = [addr.strip() for addr in to_addresses.split(",")]
            
            msg = MIMEMultipart()
            msg["Subject"] = f"[Trading System] {subject}"
            msg["From"] = self.smtp_config["from_address"]
            msg["To"] = ", ".join(to_addresses)
            
            msg.attach(MIMEText(message, "plain"))
            
            with smtplib.SMTP(
                self.smtp_config["server"],
                self.smtp_config["port"]
            ) as server:
                server.starttls()
                server.login(
                    self.smtp_config["username"],
                    self.smtp_config["password"]
                )
                server.sendmail(
                    self.smtp_config["from_address"],
                    to_addresses,
                    msg.as_string()
                )
            
            logger.info(f"Email sent successfully to {to_addresses}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
