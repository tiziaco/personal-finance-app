"""
Merchant-to-category mappings for common merchants.

Provides predefined mappings for merchants to transaction categories,
particularly focused on German/European merchants.
"""

from typing import Dict
from enum import Enum


# Import the CategoryEnum from transaction_labeler
# (or define it here if you want to make this module independent)
from app.agents.transactions_labeler.enums import CategoryEnum


def get_common_merchant_mappings() -> Dict[str, CategoryEnum]:
    """
    Get common merchant-to-category mappings for German merchants.
    Used as default mappings for German users.
    
    Returns:
        Dictionary mapping merchant names to CategoryEnum values
    """
    return {
        # Entertainment Subscriptions (Streaming Services)
        "Netflix": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Spotify": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Prime Video": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Amazon Prime": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Apple TV": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Disney+": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Sky": CategoryEnum.LEISURE_ENTERTAINMENT,
        
        # Food Delivery
        "Wolt": CategoryEnum.FOOD_DELIVERY,
        "Deliveroo": CategoryEnum.FOOD_DELIVERY,
        "Uber Eats": CategoryEnum.FOOD_DELIVERY,
        
        # Grocery Stores
        "Rewe": CategoryEnum.FOOD_GROCERIES,
        "Lidl": CategoryEnum.FOOD_GROCERIES,
        "Edeka": CategoryEnum.FOOD_GROCERIES,
        "Aldi": CategoryEnum.FOOD_GROCERIES,
        "Aldi Nord": CategoryEnum.FOOD_GROCERIES,
        "Aldi Süd": CategoryEnum.FOOD_GROCERIES,
        "Penny": CategoryEnum.FOOD_GROCERIES,
        "Netto": CategoryEnum.FOOD_GROCERIES,
        "Metro": CategoryEnum.FOOD_GROCERIES,
        "Kaufland": CategoryEnum.FOOD_GROCERIES,
        "Biomarkt": CategoryEnum.FOOD_GROCERIES,
        "Bio Company": CategoryEnum.FOOD_GROCERIES,
        "Lpg" : CategoryEnum.FOOD_GROCERIES,
        
        # Transportation
        "Db": CategoryEnum.TRANSPORTATION,
        "Bvg": CategoryEnum.TRANSPORTATION,
        "Deutsche Bahn": CategoryEnum.TRANSPORTATION,
        "Deutsche Post": CategoryEnum.TRANSPORTATION,
        "Dhl": CategoryEnum.TRANSPORTATION,
        "Flixbus": CategoryEnum.TRANSPORTATION,
        "Taxi": CategoryEnum.TRANSPORTATION,
        "Uber": CategoryEnum.TRANSPORTATION,
        "Bolt": CategoryEnum.TRANSPORTATION,
        "Tier": CategoryEnum.TRANSPORTATION,
        "Voi": CategoryEnum.TRANSPORTATION,
        "Lyft": CategoryEnum.TRANSPORTATION,
        "Shell": CategoryEnum.TRANSPORTATION,
        "Aral": CategoryEnum.TRANSPORTATION,
        "Esso": CategoryEnum.TRANSPORTATION,
        "Bp": CategoryEnum.TRANSPORTATION,
        "Total": CategoryEnum.TRANSPORTATION,
        "Ev Charging": CategoryEnum.TRANSPORTATION,
        
        # Restaurants & Bars
        "Mc Donald": CategoryEnum.BARS_RESTAURANTS,
        "Mcdonald's": CategoryEnum.BARS_RESTAURANTS,
        "Burger King": CategoryEnum.BARS_RESTAURANTS,
        "Starbucks": CategoryEnum.BARS_RESTAURANTS,
        "Subway": CategoryEnum.BARS_RESTAURANTS,
        "Pizza Hut": CategoryEnum.BARS_RESTAURANTS,
        "Dominos": CategoryEnum.BARS_RESTAURANTS,
        "Rueya": CategoryEnum.BARS_RESTAURANTS,
        "Klunkerkranich": CategoryEnum.BARS_RESTAURANTS,
        "Renate": CategoryEnum.BARS_RESTAURANTS,
        "Sage": CategoryEnum.BARS_RESTAURANTS,
        "Paloma": CategoryEnum.BARS_RESTAURANTS,
        
        # Shopping
        "Amazon": CategoryEnum.SHOPPING,
        "Amzn Mktp": CategoryEnum.SHOPPING,
        "Zalando": CategoryEnum.SHOPPING,
        "Ebay": CategoryEnum.SHOPPING,
        "Dm": CategoryEnum.SHOPPING,
        "Rossmann": CategoryEnum.SHOPPING,
        "H&M": CategoryEnum.SHOPPING,
        "Zara": CategoryEnum.SHOPPING,
        "Primark": CategoryEnum.SHOPPING,
        "Obi": CategoryEnum.SHOPPING,
        "Hornbach": CategoryEnum.SHOPPING,
        "Baumarkt": CategoryEnum.SHOPPING,
        "Poco": CategoryEnum.SHOPPING,
        "Ikea": CategoryEnum.SHOPPING,
        
        # Utilities & Household
        "Vattenfall": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Stadtwerke": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Eon": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Eon Energy": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Strom": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Gas": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Wasser": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Telekom": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Vodafone": CategoryEnum.HOUSEHOLD_UTILITIES,
        "O2": CategoryEnum.HOUSEHOLD_UTILITIES,
        "1&1": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Congstar": CategoryEnum.HOUSEHOLD_UTILITIES,
        "Fraenk": CategoryEnum.HOUSEHOLD_UTILITIES,
        
        # Healthcare & Pharmacies
        "Apotheke": CategoryEnum.HEALTHCARE_DRUG_STORES,
        "Pharmacy": CategoryEnum.HEALTHCARE_DRUG_STORES,
        "Zahnarzt": CategoryEnum.HEALTHCARE_DRUG_STORES,
        "Arzt": CategoryEnum.HEALTHCARE_DRUG_STORES,
        "Dentist": CategoryEnum.HEALTHCARE_DRUG_STORES,
        "Krankenhaus": CategoryEnum.HEALTHCARE_DRUG_STORES,
        
        # Entertainment & Leisure
        "Kino": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Cinema": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Theater": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Fitnessstudio": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Gym": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Decathlon": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Spa": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Museum": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Zoo": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Fitness": CategoryEnum.LEISURE_ENTERTAINMENT,
        "Playtomic": CategoryEnum.LEISURE_ENTERTAINMENT,
        
        # Travel & Hotels
        "Booking": CategoryEnum.TRAVEL_HOLIDAYS,
        "Airbnb": CategoryEnum.TRAVEL_HOLIDAYS,
        "Hotel": CategoryEnum.TRAVEL_HOLIDAYS,
        "Hilton": CategoryEnum.TRAVEL_HOLIDAYS,
        "Marriott": CategoryEnum.TRAVEL_HOLIDAYS,
        "Ibis": CategoryEnum.TRAVEL_HOLIDAYS,
        "Lufthansa": CategoryEnum.TRAVEL_HOLIDAYS,
        "Easyjet": CategoryEnum.TRAVEL_HOLIDAYS,
        "Ryanair": CategoryEnum.TRAVEL_HOLIDAYS,
        "Tui": CategoryEnum.TRAVEL_HOLIDAYS,
        
        # Insurance & Finance
        "Allianz": CategoryEnum.INSURANCE,
        "Axa": CategoryEnum.INSURANCE,
        "Debeka": CategoryEnum.INSURANCE,
        "Ergo": CategoryEnum.INSURANCE,
        "Versicherung": CategoryEnum.INSURANCE,
        "Bank": CategoryEnum.INSURANCE,
        "Sparkasse": CategoryEnum.INSURANCE,
        "Deutsche Bank": CategoryEnum.INSURANCE,
        "Comdirect": CategoryEnum.INSURANCE,
        "Ing": CategoryEnum.INSURANCE,
        "N26": CategoryEnum.INSURANCE,
        "Tk" : CategoryEnum.INSURANCE,  # Techniker Krankenkasse
        "Aok": CategoryEnum.INSURANCE,
        "Feather": CategoryEnum.INSURANCE,
        
        # Education
        "Vhs": CategoryEnum.EDUCATION,
        "Uni": CategoryEnum.EDUCATION,
        "Universität": CategoryEnum.EDUCATION,
        "Kurse": CategoryEnum.EDUCATION,
        "Schule": CategoryEnum.EDUCATION,
        "Udemy": CategoryEnum.EDUCATION,
        "Coursera": CategoryEnum.EDUCATION,

        # Donation & Charity
        "Sos": CategoryEnum.DONATIONS_CHARITY,

        # Savings
        "Savings": CategoryEnum.SAVINGS_INVESTMENTS,
        "Instant Savings": CategoryEnum.SAVINGS_INVESTMENTS,
    }
