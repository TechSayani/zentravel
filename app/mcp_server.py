import sys
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("zentravel_mcp")

@mcp.tool()
def get_weather(destination: str, date: str) -> str:
    """Gets the weather forecast for a destination on a specific date.

    Args:
        destination: City name.
        date: Date of travel (YYYY-MM-DD).
    """
    dest = destination.lower()
    if "tokyo" in dest:
        return f"Weather forecast for Tokyo on {date}: 22°C (72°F), Clear skies, gentle breeze. Perfect sightseeing weather!"
    elif "paris" in dest:
        return f"Weather forecast for Paris on {date}: 18°C (64°F), Light rain showers. Carry an umbrella!"
    elif "london" in dest:
        return f"Weather forecast for London on {date}: 15°C (59°F), Cloudy. High probability of fog."
    return f"Weather forecast for {destination} on {date}: 20°C (68°F), Partly cloudy. Calm weather."

@mcp.tool()
def search_flights(origin: str, destination: str, date: str) -> str:
    """Searches for available flights between origin and destination on a given date.

    Args:
        origin: Departure airport or city name.
        destination: Arrival airport or city name.
        date: Departure date (YYYY-MM-DD).
    """
    return (
        f"Available Flights from {origin} to {destination} on {date}:\n"
        f"1. Sakura Air SA-102 | Depart: 08:30 | Arrive: 15:45 | Price: $450 | Economy (Recommended)\n"
        f"2. VistaAir VA-809 | Depart: 14:00 | Arrive: 21:15 | Price: $620 | Economy\n"
        f"3. PremiumJet PJ-55 | Depart: 19:15 | Arrive: 02:30+1 | Price: $1200 | Business"
    )

@mcp.tool()
def search_hotels(destination: str, checkin_date: str, checkout_date: str) -> str:
    """Searches for available hotels in the destination city.

    Args:
        destination: City name.
        checkin_date: Check-in date (YYYY-MM-DD).
        checkout_date: Check-out date (YYYY-MM-DD).
    """
    return (
        f"Available Hotels in {destination} ({checkin_date} to {checkout_date}):\n"
        f"1. Zen Gardens Boutique Hotel | Rating: 4.8/5 | Price: $150/night | Includes breakfast\n"
        f"2. Grand Plaza Hotel | Rating: 4.5/5 | Price: $220/night | City view, pool access\n"
        f"3. BudgetStay Inn | Rating: 3.9/5 | Price: $75/night | Basic amenities, near subway"
    )

if __name__ == "__main__":
    mcp.run()
