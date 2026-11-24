import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class ExamAttemptConsumer(AsyncJsonWebsocketConsumer):
    """Real-time bidirectional WebSocket consumer for candidate examination attempts.

    Provides server-authoritative timer sync, heartbeat ticks, and proctoring event telemetry.
    """

    async def connect(self):
        self.attempt_id = self.scope['url_route']['kwargs'].get('attempt_id')
        self.room_group_name = f"exam_attempt_{self.attempt_id}"

        # Join attempt room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Send initial connection acknowledgement and timer state
        sync_payload = await self._get_attempt_sync_payload()
        if sync_payload:
            await self.send_json({
                "type": "connection_established",
                "attempt_id": str(self.attempt_id),
                "payload": sync_payload
            })
        else:
            await self.send_json({
                "type": "connection_established",
                "attempt_id": str(self.attempt_id),
                "warning": "Attempt not found or unauthenticated"
            })

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive_json(self, content):
        action = content.get('action') or content.get('type')

        if action in ('heartbeat', 'timer_sync', 'ping'):
            sync_payload = await self._get_attempt_sync_payload()
            await self.send_json({
                "type": "timer_sync",
                "server_time": timezone.now().isoformat(),
                "payload": sync_payload
            })

        elif action == 'proctoring_event':
            event_type = content.get('event_type', 'TAB_SWITCH')
            details = content.get('details', {})
            await self._log_proctoring_event(event_type, details)
            await self.send_json({
                "type": "proctoring_ack",
                "event_type": event_type,
                "server_time": timezone.now().isoformat()
            })

        else:
            await self.send_json({
                "type": "ack",
                "server_time": timezone.now().isoformat()
            })

    @sync_to_async
    def _get_attempt_sync_payload(self):
        from .models import ExaminationAttempt, AttemptStatus
        try:
            attempt = ExaminationAttempt.objects.select_related('examination').get(id=self.attempt_id)
            now = timezone.now()
            remaining = attempt.remaining_seconds
            is_active = attempt.status == AttemptStatus.IN_PROGRESS and remaining > 0
            return {
                "remaining_seconds": remaining,
                "server_deadline": attempt.server_deadline.isoformat(),
                "status": attempt.status,
                "is_active": is_active,
                "server_time": now.isoformat(),
            }
        except Exception:
            return None

    @sync_to_async
    def _log_proctoring_event(self, event_type, details):
        from .models import ExaminationAttempt, ProctoringLog, ProctoringEventType
        try:
            attempt = ExaminationAttempt.objects.get(id=self.attempt_id)
            ev = getattr(ProctoringEventType, event_type, ProctoringEventType.TAB_SWITCH)
            ProctoringLog.objects.create(
                attempt=attempt,
                event_type=ev,
                details=details
            )
            if ev == ProctoringEventType.TAB_SWITCH:
                attempt.tab_switch_count += 1
                attempt.save(update_fields=['tab_switch_count', 'updated_at'])
        except Exception as e:
            logger.warning(f"Error logging proctoring event over WS: {e}")
