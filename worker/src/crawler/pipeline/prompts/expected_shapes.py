from schema import And, Or, Schema

ExpectedBooking = Schema(
    {
        "ok": bool,
        "booking_method": And(
            str,
            lambda s: s
            in {
                "Online Booking",
                "Form Submission",
                "Contact Info",
                "Cannot Infer",
            },
        ),
    },
    ignore_extra_keys=False,
)

ExpectedLanding = Schema(
    {
        "ok": bool,
        "is_experience": bool,
        "belongs_to_specified_operator": bool,
        "classification": Or(
            None,
            {
                "operator_type": And(
                    str,
                    lambda s: s
                    in {
                        "Activity",
                        "Attraction",
                        "Event",
                        "Tour",
                        "Transportation",
                    },
                ),
                "business_type": And(
                    str,
                    lambda s: s
                    in {
                        "Air-based adventure, activity, or rentals",
                        "Cultural activity, experience or classes",
                        "Land-based adventure, activity, or rentals",
                        "Water-based adventure, activity, or rentals",
                        "Wellness",
                        "Amusement & Theme Parks",
                        "Cultural Sites & Landmarks",
                        "Museums & Galleries",
                        "Natural Attraction",
                        "Observation Decks & Towers",
                        "Zoos & Aquariums",
                        "Festivals",
                        "Performing arts",
                        "Sporting event",
                        "Active / adventure",
                        "Boat Tours",
                        "Cultural & Specialty Tours",
                        "Food & Drink",
                        "Multi-day Tours",
                        "Sightseeing",
                        "Tour of a specific attraction",
                        "Transportation",
                    },
                ),
            },
        ),
        "is_commercial_operator": Or(None, bool),
        "booking_method": Or(
            None,
            And(
                str,
                lambda s: s
                in {
                    "Online Booking",
                    "Form Submission",
                    "Contact Info",
                    "Cannot Infer",
                },
            ),
        ),
        "operating_scope": Or(
            None,
            And(str, lambda s: s in {"local", "multi_regional", "international"}),
        ),
        "follow_contact": Or(None, str),
        "follow_booking": Or(None, str),
    },
    ignore_extra_keys=False,
)

ExpectedProfiles = Schema(
    {
        "ok": bool,
        "profiles": [
            {
                "profile_type": And(
                    str,
                    lambda s: s in {"Company", "Individual"},
                ),
                "role": Or(
                    None,
                    And(
                        str,
                        lambda s: s
                        in {
                            "Owner",
                            "Manager",
                            "Guide",
                            "Booking Agent",
                            "Support",
                            "Unknown",
                        },
                    ),
                ),
                "individual_name": Or(None, str),
                "email": Or(None, str),
                "phone": Or(None, str),
                "whatsapp": Or(None, str),
            }
        ]
    },
    ignore_extra_keys=False,
)