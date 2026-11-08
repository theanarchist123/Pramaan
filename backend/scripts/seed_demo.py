"""Seed a clearly-fictional demo registry (36 people) so search, the network and the map have content.

Every person, institution and award here is invented; profiles are flagged is_demo=True and the UI
labels them "Demo". Also creates the demo admin:  admin@pramaan.demo / pramaan-demo-1

Run:  .venv\\Scripts\\python.exe scripts\\seed_demo.py
"""
import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import dispose_engine, get_sessionmaker, init_db  # noqa: E402
from app.domain import pick_photo  # noqa: E402
from app.models import Claim, Consent, Evidence, Profile, User  # noqa: E402
from app.services.certificates import issue_certificate  # noqa: E402
from app.services.directory import rebuild_graph, reindex_all  # noqa: E402

# Fictional institutions (shared between people → real edges in the network)
KAVERI = "Kaveri Institute of Science"
SAHYADRI = "Sahyadri Marine Research Centre"
THAR = "Thar Solar Foundation"
BRAHMA = "Brahmaputra Technical University"
DECCAN = "Deccan School of Design"
VAIGAI = "Vaigai College of Arts"
GANGA = "Ganga Basin Public Health Trust"
NILGIRI = "Nilgiri Open University"
KONKAN = "Konkan Maritime Institute"
HIMAL = "Himalayan Heritage Society"

# name, sector, state, city, headline, institutions, bio, [(field, value, year, status)]
D, W = "document", "web"
PEOPLE = [
    ("Ananya Rekhi", "Energy", "Karnataka", "Bengaluru", "Perovskite solar-cell researcher", [KAVERI, THAR],
     "Ananya leads a lab developing low-cost perovskite solar cells for rural microgrids.",
     [("award", "Kaveri Prize for Clean-Energy Research", 2024, D), ("position", "Principal Investigator, Kaveri Solar Lab", 2021, W)]),
    ("Vikram Hosamani", "Energy", "Karnataka", "Mysuru", "Rooftop-solar entrepreneur", [KAVERI],
     "Vikram built a rooftop-solar installer network across twelve districts in Karnataka.",
     [("achievement", "Founded SunGrama, installing solar in 3,000 village homes", 2019, W), ("award", "Karnataka Clean Energy Entrepreneur Award", 2023, D)]),
    ("Dr. Shalini Bhogle", "Energy", "Karnataka", "Dharwad", "Battery-storage engineer collaborating with universities", [KAVERI, NILGIRI],
     "Shalini designs grid-scale battery storage and runs joint projects with three universities.",
     [("publication", "Co-authored study on sodium-ion storage with Nilgiri Open University", 2022, W), ("position", "Head of Storage Research, Kaveri Institute", 2020, D)]),
    ("Pradeep Chauhan", "Energy", "Rajasthan", "Jodhpur", "Desert solar-farm planner", [THAR],
     "Pradeep plans utility-scale solar farms in the Thar desert with a focus on water-free cleaning.",
     [("achievement", "Led a 400 MW desert solar project to completion", 2022, W), ("award", "Thar Solar Foundation Fellowship", 2021, D)]),
    ("Meenakshi Subbiah", "Energy", "Tamil Nadu", "Tirunelveli", "Wind-power engineer", [VAIGAI],
     "Meenakshi optimises coastal wind farms and trains local technicians.",
     [("achievement", "Commissioned 120 MW of coastal wind capacity", 2020, W)]),
    ("Dr. Rohan Aranha", "Science", "Kerala", "Kochi", "Marine biologist studying coral resilience", [SAHYADRI],
     "Rohan studies how coral reefs recover after heatwaves along the Malabar coast.",
     [("award", "Sagar Research Medal", 2024, D), ("publication", "Published a decade-long study of Lakshadweep coral recovery", 2023, W)]),
    ("Devika Nambiar", "Science", "Kerala", "Thiruvananthapuram", "Ocean-current modeller", [SAHYADRI, KAVERI],
     "Devika builds forecasting models of coastal ocean currents used by fishing communities.",
     [("position", "Senior Scientist, Sahyadri Marine Research Centre", 2019, D), ("achievement", "Launched a fishermen's ocean-forecast SMS service", 2021, W)]),
    ("Prof. Imran Sheikhani", "Science", "Maharashtra", "Pune", "Astrophysicist and science communicator", [DECCAN],
     "Imran researches pulsar timing and runs a popular public astronomy programme.",
     [("award", "Deccan Science Communication Award", 2022, D), ("publication", "Authored 'A Sky for Everyone', a children's astronomy book", 2021, W)]),
    ("Tanvi Kulkarni-Rao", "Technology", "Maharashtra", "Mumbai", "Founder of a vernacular-AI startup", [DECCAN],
     "Tanvi builds speech technology for Indian languages with low-bandwidth support.",
     [("achievement", "Founded VaniLabs, serving speech AI in 11 Indian languages", 2020, W), ("award", "Deccan Innovators Award", 2023, D)]),
    ("Arvind Gollapudi", "Technology", "Telangana", "Hyderabad", "Cybersecurity engineer", [NILGIRI],
     "Arvind leads open-source tooling for securing public-sector software.",
     [("position", "Director of Security Engineering at a public digital-infrastructure body", 2021, W), ("achievement", "Created an open-source vulnerability scanner used by 40 agencies", 2022, W)]),
    ("Sneha Pattanaik", "Technology", "Odisha", "Bhubaneswar", "Open-data civic technologist", [BRAHMA],
     "Sneha builds open-data dashboards that help districts track public services.",
     [("achievement", "Built a district-service dashboard adopted in 14 districts", 2022, W)]),
    ("Dr. Lakshmi Venkataraghavan", "Healthcare", "Tamil Nadu", "Chennai", "Paediatric cardiologist", [NILGIRI],
     "Lakshmi pioneered a low-cost screening programme for congenital heart disease in children.",
     [("award", "Nilgiri Medal for Child Health", 2023, D), ("achievement", "Screened 60,000 children for congenital heart disease", 2022, W)]),
    ("Dr. Bhaskar Dutta", "Healthcare", "West Bengal", "Kolkata", "Public-health epidemiologist", [GANGA],
     "Bhaskar tracks waterborne disease outbreaks across the Ganga basin.",
     [("position", "Chief Epidemiologist, Ganga Basin Public Health Trust", 2020, D), ("publication", "Published an outbreak early-warning method for cholera", 2021, W)]),
    ("Nandini Barua", "Healthcare", "Assam", "Guwahati", "Rural telemedicine pioneer", [BRAHMA, GANGA],
     "Nandini runs a telemedicine network connecting river-island villages to specialists.",
     [("achievement", "Connected 85 river-island villages to specialist doctors", 2021, W), ("award", "Brahmaputra Health Innovation Award", 2022, D)]),
    ("Prof. Kamala Ranganathan", "Education", "Karnataka", "Bengaluru", "Mathematics educator", [KAVERI],
     "Kamala developed a play-based mathematics curriculum now used in 900 government schools.",
     [("achievement", "Designed a mathematics curriculum adopted by 900 government schools", 2018, W), ("award", "Kaveri Teaching Excellence Award", 2020, D)]),
    ("Suresh Kharbanda", "Education", "Meghalaya", "Shillong", "Community-school founder", [BRAHMA],
     "Suresh founded schools in remote hill villages taught in the local language.",
     [("achievement", "Founded 22 community schools in hill villages", 2017, W)]),
    ("Ritu Sandhu", "Arts & Culture", "Punjab", "Amritsar", "Folk musician and archivist", [HIMAL],
     "Ritu records and teaches vanishing Punjabi folk songs.",
     [("achievement", "Archived 500 endangered folk songs", 2022, W), ("award", "Himalayan Heritage Cultural Award", 2023, D)]),
    ("Gopal Krishnamurthy", "Arts & Culture", "Tamil Nadu", "Madurai", "Bharatanatyam teacher", [VAIGAI],
     "Gopal teaches classical dance to children from low-income families.",
     [("position", "Principal, Vaigai School of Classical Dance", 2015, D), ("achievement", "Trained 800 students at no fee", 2022, W)]),
    ("Farah Mirza", "Arts & Culture", "Delhi", "New Delhi", "Contemporary painter", [DECCAN],
     "Farah's large-scale paintings explore migration and memory.",
     [("achievement", "Solo exhibition at a national gallery", 2023, W)]),
    ("Jyotirmoy Sarkar", "Literature", "West Bengal", "Kolkata", "Novelist and translator", [VAIGAI],
     "Jyotirmoy writes in Bengali and translates between Bengali and English.",
     [("publication", "Published the novel 'River Without Banks'", 2020, W), ("award", "Vaigai Literary Prize for Translation", 2022, D)]),
    ("Anjali Deshpande", "Literature", "Maharashtra", "Nagpur", "Marathi poet", [DECCAN],
     "Anjali's poetry collections are taught in several state universities.",
     [("publication", "Published three Marathi poetry collections", 2021, W)]),
    ("Harpreet Gill", "Sports", "Punjab", "Ludhiana", "Hockey coach and former international", [HIMAL],
     "Harpreet coaches village hockey academies and has produced several national players.",
     [("achievement", "Coached a state team to a national championship", 2022, W), ("award", "State Lifetime Coaching Award", 2023, D)]),
    ("Mary Kynsai", "Sports", "Meghalaya", "Shillong", "Archery champion", [BRAHMA],
     "Mary won multiple national archery titles and now mentors young archers.",
     [("award", "National Archery Championship, Gold", 2021, D)]),
    ("Rajiv Thakkar", "Business", "Gujarat", "Ahmedabad", "Textile entrepreneur", [DECCAN],
     "Rajiv leads a textile cooperative of 2,000 women weavers.",
     [("position", "Chair, Women Weavers' Cooperative", 2018, W), ("achievement", "Grew the cooperative's exports to 14 countries", 2022, W)]),
    ("Lata Parmar", "Business", "Gujarat", "Surat", "Social-enterprise founder", [KAVERI],
     "Lata founded a recycling enterprise employing waste pickers as shareholders.",
     [("achievement", "Founded a waste-picker-owned recycling company", 2019, W)]),
    ("Dr. Vinod Chaudhary", "Public Service", "Uttar Pradesh", "Lucknow", "Civil servant focused on rural governance", [NILGIRI],
     "Vinod led a district-level programme digitising land records for smallholders.",
     [("position", "District Magistrate (Rural Development)", 2019, W), ("achievement", "Digitised land records for 300,000 smallholders", 2020, W)]),
    ("Aditi Menon", "Public Service", "Delhi", "New Delhi", "Policy researcher on urban housing", [KAVERI],
     "Aditi advises city governments on affordable housing policy.",
     [("publication", "Authored a national report on rental housing reform", 2022, W)]),
    ("Adv. Sabina Qureshi", "Law", "Delhi", "New Delhi", "Constitutional lawyer", [NILGIRI],
     "Sabina litigates in access-to-justice and public-interest cases.",
     [("achievement", "Argued landmark public-interest cases on legal aid", 2021, W), ("award", "National Legal Aid Service Award", 2023, D)]),
    ("Justice (Retd.) Ramanathan Iyer", "Law", "Tamil Nadu", "Chennai", "Retired high-court judge and mediator", [VAIGAI],
     "Ramanathan now mentors young mediators and writes on judicial reform.",
     [("position", "Judge of a High Court (retired)", 2012, W)]),
    ("Shreya Bandyopadhyay", "Media", "West Bengal", "Kolkata", "Investigative journalist", [GANGA],
     "Shreya reports on river pollution and its effects on fishing communities.",
     [("achievement", "Exposed illegal industrial discharge into a river", 2021, W), ("award", "Press Excellence Award for Environmental Reporting", 2022, D)]),
    ("Dhruv Saikia", "Media", "Assam", "Dibrugarh", "Radio broadcaster", [BRAHMA],
     "Dhruv hosts community radio in Assamese and Bodo.",
     [("achievement", "Launched a community radio station covering 200 villages", 2018, W)]),
    ("Rukmini Sahoo", "Social Work", "Odisha", "Puri", "Disaster-resilience organiser", [GANGA, BRAHMA],
     "Rukmini trains coastal communities in cyclone preparedness.",
     [("achievement", "Trained 400 villages in cyclone preparedness", 2020, W), ("award", "Coastal Resilience Citizen Award", 2022, D)]),
    ("Iqbal Hussain Lone", "Social Work", "Telangana", "Hyderabad", "Foster-care advocate", [NILGIRI],
     "Iqbal built a network of foster families for children leaving institutional care.",
     [("achievement", "Placed 350 children with foster families", 2022, W)]),
    ("Chandrakant Waghmare", "Agriculture", "Maharashtra", "Nashik", "Drip-irrigation farmer-innovator", [DECCAN],
     "Chandrakant adapted drip irrigation for small onion and grape farms, cutting water use by half.",
     [("achievement", "Cut farm water use 50% with a low-cost drip system", 2019, W), ("award", "State Progressive Farmer Award", 2021, D)]),
    ("Bimala Thakuri", "Agriculture", "Himachal Pradesh", "Mandi", "Organic apple grower and cooperative leader", [HIMAL],
     "Bimala leads a cooperative of organic apple growers in the hills.",
     [("position", "President, Hill Organic Growers' Cooperative", 2018, W)]),
    ("Dr. Salim Ansari", "Science", "Uttar Pradesh", "Kanpur", "Materials scientist", [KAVERI, DECCAN],
     "Salim develops biodegradable packaging from agricultural waste.",
     [("award", "Young Materials Scientist Award", 2022, D), ("publication", "Published a biodegradable packaging process from rice husk", 2021, W)]),
    ("Pooja Rathore", "Technology", "Rajasthan", "Jaipur", "Edtech founder", [THAR, DECCAN],
     "Pooja built an offline-first learning app for schools without reliable internet.",
     [("achievement", "Built an offline learning app used in 5,000 schools", 2021, W)]),
]


async def main() -> None:
    await init_db()
    async with get_sessionmaker()() as s:
        if (await s.execute(select(Profile).where(Profile.is_demo.is_(True)).limit(1))).scalar_one_or_none():
            print("Demo data already present — nothing to do.")
            await dispose_engine()
            return

        if (await s.execute(select(User).where(User.email == "admin@pramaan.demo"))).scalar_one_or_none() is None:
            s.add(User(email="admin@pramaan.demo", name="Demo Admin", role="admin", password_hash=hash_password("pramaan-demo-1")))

        for i, (name, sector, state, city, headline, insts, bio, claims) in enumerate(PEOPLE):
            slug = "demo-" + "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")[:50]
            p = Profile(
                slug=slug, full_name=name, headline=headline, sector=sector, state=state, city=city, bio=bio,
                institutions=insts, languages=["English"], status="approved", is_demo=True,
            )
            for field, value, year, status in claims:
                c = Claim(field=field, value=value, year=year, status=status, confidence=0.97 if status == D else 0.85)
                c.evidence.append(
                    Evidence(kind=status, quote=value, url="" if status == D else "https://example.org/demo-source")
                )
                p.claims.append(c)
            s.add(p)
            await s.flush()
            s.add(Consent(profile_id=p.id, kind="public_listing", granted=True, text="Fictional demo profile."))
            cert = await issue_certificate(s, p)
            cert.photo_id = pick_photo(p.sector, cert.digest)

        await s.flush()
        n = await reindex_all(s)
        e = await rebuild_graph(s)
        await s.commit()
        print(f"Seeded {len(PEOPLE)} fictional profiles + certificates; indexed {n}, {e} relationships.")
        print("Demo admin: admin@pramaan.demo / pramaan-demo-1  (change before any real deployment)")
    await dispose_engine()


asyncio.run(main())
