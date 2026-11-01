from __future__ import annotations

from typing import Optional
from models import EventState

VENDOR_SYSTEM_PROMPT = (
    "You are a forensic event contract auditor and procurement specialist in India. "
    "You examine vendor quotations, messages, and invoices to uncover hidden charges, "
    "verify deliverables, check GST/tax compliance, and structure clear payment schedules."
)


def vendor_parse_prompt(
    raw_text: str,
    category: str,
    state: Optional[EventState] = None,
) -> str:
    """
    Generate the prompt for auditing and structuring a vendor quote.

    Rules applied:
    - Injects the full current EventState as JSON (if session is active).
    - Scrutinizes raw vendor text for Indian event hidden charges (GST 18%, diesel generator fuel,
      corkage, extra hour fees, cleanup, service charges, mandatory decor royalties).
    - Structures inclusions, exclusions, itemized line items in ₹, and payment schedules.
    - Flags whether quote is verified (default false until signed).
    - "Return ONLY valid JSON. No markdown, no explanation."
    """
    state_section = (
        f"FULL EVENT STATE:\n{state.model_dump_json(indent=2)}\n"
        if state is not None
        else "EVENT STATE CONTEXT: Standalone vendor quote audit."
    )

    return f"""{state_section}

VENDOR CATEGORY HINT: {category}

RAW VENDOR PROPOSAL / QUOTATION TEXT:
\"\"\"
{raw_text}
\"\"\"

AUDIT & PARSING INSTRUCTIONS:
1. Extract Vendor Identity & Core Figures:
   - 'vendor_name': Vendor or agency commercial name.
   - 'category': Service category (e.g., catering, venue, decor, photography, entertainment).
   - 'total_quoted': Grand total amount in INR (₹). Ensure taxes are factored in if stated.
   - 'capacity': Guest headcount or unit capacity (integer or null if not applicable).
   - 'payment_schedule': Terms of advance, milestone payments, and final settlement (e.g., '25% advance on booking, 50% 1 week prior, 25% post-event').
   - 'is_verified': false (quote is under review, not yet contractually executed).

2. Rigorous Indian Market Audit:
   - 'line_items': List of itemized components with description and amount in ₹.
   - 'hidden_fees': Uncover subtle charges commonly found in Indian events:
     * 18% GST / luxury taxes omitted from headline rates.
     * Generator diesel fuel surcharge or electricity meter fees.
     * Venue corkage or external caterer royalty fees.
     * Overtime charges beyond 11:00 PM per hour.
     * Service staff gratuity / compulsory union loading fees.
   - 'inclusions': Explicitly guaranteed materials, staff, and services provided.
   - 'exclusions': Explicitly omitted supplies (e.g., packaged drinking water, DJ sound console, flower transport).
   - 'notes': Strategic negotiation leverage points and contract recommendations.

Return ONLY valid JSON. No markdown, no explanation.
"""

