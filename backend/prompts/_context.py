from __future__ import annotations

"""
Shared Indian-grounding context block injected into every prompt.
Import INDIA_CONTEXT and prepend / append it to system or user prompts.
"""

INDIA_CONTEXT = """\
=== MANDATORY INDIAN EVENT CONTEXT — FOLLOW STRICTLY ===

1. LOCATION & MARKET: This event is in India (primarily Bangalore / South India).
   Use ONLY realistic Bangalore / South-India market pricing in ₹ (INR).
   Prefer local Indian vendors, South Indian cuisine options, and common practices
   in Bangalore.

2. CULTURALLY APPROPRIATE TASKS ONLY — DO NOT suggest:
   - Airport or railway-station guest pickups / shuttle fleets
   - Western-style DJ packages or rave lighting (a simple sound system is fine)
   - Makeup artist (ONLY for weddings or sangeet — never for birthday parties)
   - Valet parking service
   - Imported floral arrangements as the default (Indian marigold / tuberose / jasmine are standard)
   - Cocktail / alcohol bars (unless user explicitly requests)
   - Western dessert bars (stick to Indian mithai, fruit bowls, ice-cream counters)

3. EVENT-TYPE SPECIFIC RULES:

   BIRTHDAY PARTY (any age, especially toddler / kids / 1st birthday):
   Focus ONLY on these 8 categories (map every task and budget item to one of these):
     a. Venue booking — community hall, club house, hotel banquet, terrace (Bangalore rates)
     b. Catering — Indian finger foods, chaat, South-Indian snacks, meal for adults
     c. Birthday cake — custom theme cake from local Bangalore bakeries (₹1,000–₹5,000)
     d. Decoration — balloon setup, theme backdrop, flower decoration, lighting
     e. Photography — candid photographer / basic video for memories
     f. Return gifts — small goody bags / chocolates / small toys for children
     g. Invitation cards — digital WhatsApp invite + optional printed cards
     h. Sound system — light background music setup, NOT a full DJ rig

   WEDDING:
   Include: mandap, mehendi, sangeet, haldi (if requested), Indian catering (vegetarian +
   non-veg options), photography + videography, invitation cards, decor (floral / draping),
   baraat logistics, priest (purohit) booking, bridal attire (not makeup artist as a budget
   category unless explicit).

   CORPORATE EVENT:
   Include: banquet / conference hall, vegetarian catering, AV system, corporate gifting,
   event anchor / emcee, branding / standees, photography.

   COMMUNITY / FESTIVAL EVENT:
   Include: open ground / community hall, mass catering (₹150–₹350 per plate typical),
   stage + sound, cultural program coordination, volunteer management.

4. PRICING GUIDE (approximate Bangalore 2025 market rates):
   - Community / club hall rental: ₹15,000–₹60,000 per day
   - Hotel banquet (small, 50 pax): ₹20,000–₹80,000
   - Catering per plate (South-Indian veg): ₹250–₹600
   - Birthday cake (theme, 1–3 kg): ₹1,000–₹5,000
   - Balloon / theme decoration: ₹5,000–₹30,000
   - Candid photographer (1 day): ₹8,000–₹25,000
   - Return gift (per child): ₹100–₹300
   - Printed invitation cards (50 pcs): ₹1,500–₹5,000
   - Sound system (light music, 4 hrs): ₹3,000–₹10,000

5. LANGUAGE: Keep all descriptions practical, concise, and culturally appropriate.
   Use ₹ (not $) for all amounts.

=== END OF CONTEXT ===
"""

