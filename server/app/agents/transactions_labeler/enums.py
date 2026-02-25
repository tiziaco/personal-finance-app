# NOTE: Keep in sync with app/models/transaction.CategoryEnum.
# This copy exists so the agent layer does not import from the DB model layer.
from enum import Enum


class CategoryEnum(str, Enum):
    """Predefined spending categories for transaction classification."""

    INCOME = "Income"
    TRANSPORTATION = "Transportation"
    SALARY = "Salary"
    HOUSEHOLD_UTILITIES = "Household & Utilities"
    TAX_FINES = "Tax & Fines"
    MISCELLANEOUS = "Miscellaneous"
    FOOD_GROCERIES = "Food & Groceries"
    FOOD_DELIVERY = "Food Delivery"
    ATM = "ATM"
    INSURANCE = "Insurances"
    SHOPPING = "Shopping"
    BARS_RESTAURANTS = "Bars & Restaurants"
    EDUCATION = "Education"
    FAMILY_FRIENDS = "Family & Friends"
    DONATIONS_CHARITY = "Donations & Charity"
    HEALTHCARE_DRUG_STORES = "Healthcare & Drug Stores"
    LEISURE_ENTERTAINMENT = "Leisure & Entertainment"
    MEDIA_ELECTRONICS = "Media & Electronics"
    SAVINGS_INVESTMENTS = "Savings & Investments"
    TRAVEL_HOLIDAYS = "Travel & Holidays"
