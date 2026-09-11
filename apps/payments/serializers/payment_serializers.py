import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.bookings.models import Booking, BookingStatus, PaymentType
from apps.payments.models import (
    PaymentTransaction,
    PaymentGateway,
    PaymentStage,
    PaymentStatus,
)


class PaymentTransactionReadSerializer(serializers.ModelSerializer):
    """
    Receipt and transaction history serializer.
    """

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "transaction_id",
            "gateway",
            "payment_stage",
            "amount",
            "currency",
            "charged_amount",
            "charged_currency",
            "exchange_rate",
            "gateway_fee",
            "status",
            "processed_at",
            "created_at",
        ]
        read_only_fields = fields


class PaymentInitiateSerializer(serializers.Serializer):
    """
    Serializer to initiate a checkout session with Khalti or Stripe.
    Validates booking balance and locks exchange rate.
    """

    booking_id = serializers.UUIDField(required=True)
    gateway = serializers.ChoiceField(choices=PaymentGateway.choices)
    payment_stage = serializers.ChoiceField(choices=PaymentStage.choices)

    def validate(self, attrs):
        booking_id = attrs.get("booking_id")
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            raise serializers.ValidationError({"booking_id": "Booking not found."})

        if booking.status in [BookingStatus.CANCELLED, BookingStatus.REFUNDED]:
            raise serializers.ValidationError(f"Cannot process payment for booking with status {booking.status}.")

        stage = attrs.get("payment_stage")
        if stage == PaymentStage.DEPOSIT_20:
            if booking.status != BookingStatus.PENDING:
                raise serializers.ValidationError("Deposit can only be initiated for pending bookings.")
            attrs["amount"] = booking.deposit_amount_usd
        elif stage == PaymentStage.BALANCE_80:
            if booking.status != BookingStatus.DEPOSIT_PAID:
                raise serializers.ValidationError("Balance payment requires deposit to have been paid.")
            attrs["amount"] = booking.balance_amount_usd
        elif stage == PaymentStage.FULL_100:
            attrs["amount"] = booking.total_amount_usd
        else:
            attrs["amount"] = booking.balance_amount_usd

        attrs["booking"] = booking
        return attrs

    def create(self, validated_data):
        booking = validated_data["booking"]
        gateway = validated_data["gateway"]
        stage = validated_data["payment_stage"]
        amount = validated_data["amount"]

        # Default exchange rate USD -> NPR (e.g. 133.50)
        exchange_rate = Decimal("133.50")
        charged_amount = (amount * exchange_rate).quantize(Decimal("0.01"))
        txn_id = f"TXN-{gateway[:3]}-{uuid.uuid4().hex[:10].upper()}"

        transaction_obj = PaymentTransaction.objects.create(
            booking=booking,
            transaction_id=txn_id,
            gateway=gateway,
            payment_stage=stage,
            amount=amount,
            currency="USD",
            exchange_rate=exchange_rate,
            charged_amount=charged_amount,
            charged_currency="NPR",
            status=PaymentStatus.INITIATED,
        )

        checkout_url = f"https://payment.dreamscape-treks.com/checkout/{gateway.lower()}/{txn_id}"
        return {
            "transaction_id": txn_id,
            "checkout_url": checkout_url,
            "amount": amount,
            "currency": "USD",
            "charged_amount": charged_amount,
            "charged_currency": "NPR",
            "payment_stage": stage,
        }


class PaymentWebhookSerializer(serializers.Serializer):
    """
    Webhook handler serializer for Khalti and Stripe asynchronous payment notifications.
    Ensures idempotency and updates booking state atomically.
    """

    transaction_id = serializers.CharField(required=True)
    gateway_status = serializers.CharField(required=True)  # e.g. "Completed", "succeeded"
    idempotency_key = serializers.CharField(required=False, allow_blank=True)
    raw_payload = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        txn_id = attrs["transaction_id"]
        try:
            txn = PaymentTransaction.objects.select_related("booking").get(transaction_id=txn_id)
            attrs["payment_transaction"] = txn
        except PaymentTransaction.DoesNotExist:
            raise serializers.ValidationError({"transaction_id": "Payment transaction not found."})

        idemp_key = attrs.get("idempotency_key")
        if idemp_key:
            if PaymentTransaction.objects.filter(idempotency_key=idemp_key).exclude(id=txn.id).exists():
                raise serializers.ValidationError({"idempotency_key": "Webhook already processed (duplicate key)."})

        return attrs

    def save(self):
        txn = self.validated_data["payment_transaction"]
        gateway_status = self.validated_data["gateway_status"].upper()
        raw_payload = self.validated_data.get("raw_payload", {})
        idemp_key = self.validated_data.get("idempotency_key")

        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(id=txn.booking_id)

            if gateway_status in ["COMPLETED", "SUCCEEDED", "SUCCESS"]:
                txn.status = PaymentStatus.SUCCESS
                txn.processed_at = timezone.now()
                txn.webhook_raw_payload = raw_payload
                if idemp_key:
                    txn.idempotency_key = idemp_key
                txn.save()

                # Update booking balances
                booking.amount_paid_usd += txn.amount
                booking.balance_amount_usd = max(Decimal("0.00"), booking.total_amount_usd - booking.amount_paid_usd)

                if booking.amount_paid_usd >= booking.total_amount_usd:
                    booking.status = BookingStatus.FULLY_PAID
                elif booking.payment_type == PaymentType.DEPOSIT_20 and booking.amount_paid_usd >= booking.deposit_amount_usd:
                    booking.status = BookingStatus.DEPOSIT_PAID

                booking.save(update_fields=["amount_paid_usd", "balance_amount_usd", "status", "updated_at"])
            else:
                txn.status = PaymentStatus.FAILED
                txn.processed_at = timezone.now()
                txn.webhook_raw_payload = raw_payload
                txn.save()

        return txn
