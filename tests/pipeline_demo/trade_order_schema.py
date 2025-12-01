from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class TradeOrder:
    order_id: str
    timestamp_utc: str
    wallet: str
    network: str
    token_in_symbol: str
    token_in_mint: str
    token_out_symbol: str
    token_out_mint: str
    side: str
    mode: str
    in_amount_sol: float
    in_amount_lamports: int
    expected_out_amount: float
    slippage_bps: int
    max_slippage_pct: float
    priority_fee_sol: float
    is_anti_mev: bool
    partner: str
    rl_score: float
    sentiment_score: float
    kalman_signal: float
    jumpdiff_signal: float
    rbergomi_signal: float
    final_decision: str
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "timestamp_utc": self.timestamp_utc,
            "wallet": self.wallet,
            "network": self.network,
            "token_in_symbol": self.token_in_symbol,
            "token_in_mint": self.token_in_mint,
            "token_out_symbol": self.token_out_symbol,
            "token_out_mint": self.token_out_mint,
            "side": self.side,
            "mode": self.mode,
            "in_amount_sol": self.in_amount_sol,
            "in_amount_lamports": self.in_amount_lamports,
            "expected_out_amount": self.expected_out_amount,
            "slippage_bps": self.slippage_bps,
            "max_slippage_pct": self.max_slippage_pct,
            "priority_fee_sol": self.priority_fee_sol,
            "is_anti_mev": self.is_anti_mev,
            "partner": self.partner,
            "rl_score": self.rl_score,
            "sentiment_score": self.sentiment_score,
            "kalman_signal": self.kalman_signal,
            "jumpdiff_signal": self.jumpdiff_signal,
            "rbergomi_signal": self.rbergomi_signal,
            "final_decision": self.final_decision,
            "reasoning": self.reasoning,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "TradeOrder":
        return TradeOrder(
            order_id=data["order_id"],
            timestamp_utc=data["timestamp_utc"],
            wallet=data["wallet"],
            network=data["network"],
            token_in_symbol=data["token_in_symbol"],
            token_in_mint=data["token_in_mint"],
            token_out_symbol=data["token_out_symbol"],
            token_out_mint=data["token_out_mint"],
            side=data["side"],
            mode=data["mode"],
            in_amount_sol=float(data["in_amount_sol"]),
            in_amount_lamports=int(data["in_amount_lamports"]),
            expected_out_amount=float(data["expected_out_amount"]),
            slippage_bps=int(data["slippage_bps"]),
            max_slippage_pct=float(data["max_slippage_pct"]),
            priority_fee_sol=float(data["priority_fee_sol"]),
            is_anti_mev=bool(data["is_anti_mev"]),
            partner=data["partner"],
            rl_score=float(data["rl_score"]),
            sentiment_score=float(data["sentiment_score"]),
            kalman_signal=float(data["kalman_signal"]),
            jumpdiff_signal=float(data["jumpdiff_signal"]),
            rbergomi_signal=float(data["rbergomi_signal"]),
            final_decision=data["final_decision"],
            reasoning=data["reasoning"],
        )


def build_dummy_trade_order() -> TradeOrder:
    """
    Return a TradeOrder instance filled with the exact dummy values from the spec.
    """
    return TradeOrder(
        order_id="demo-20251201-0001",
        timestamp_utc="2025-12-01T14:23:45Z",
        wallet="7aQFqQ8uD2wLQkYqgqN9pksxvQwPjZ7hV1pLQ5J9PNhn",
        network="solana",
        token_in_symbol="SOL",
        token_in_mint="So11111111111111111111111111111111111111112",
        token_out_symbol="PEPE56",
        token_out_mint="Cmx4T7rDorV5dSnc9wVSaKzAiy6ufh5BRbaru12Zpump",
        side="BUY",
        mode="ExactIn",
        in_amount_sol=0.75,
        in_amount_lamports=750000000,
        expected_out_amount=1234567.89,
        slippage_bps=1000,
        max_slippage_pct=10.0,
        priority_fee_sol=0.0005,
        is_anti_mev=True,
        partner="POLYO_PIPELINE",
        rl_score=0.78,
        sentiment_score=0.72,
        kalman_signal=0.41,
        jumpdiff_signal=0.35,
        rbergomi_signal=0.52,
        final_decision="EXECUTE",
        reasoning="Strong positive sentiment on PEPE56, acceptable liquidity, no hard rug flags, quant signals moderately bullish. Size capped at 0.75 SOL due to risk limits.",
    )
