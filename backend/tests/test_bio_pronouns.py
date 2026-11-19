"""A bio never guesses someone's gender. The live site showed a model-written bio calling a member "He" from their name alone (2026-11-19).
A bio with he/she/his/her is kept only when the person said which pronouns they use; otherwise it is dropped and Saathi writes it again."""
import pytest

from app.services.onboarding import bio_without_guessed_gender


@pytest.mark.parametrize("bio,said,keep", [
    ("Meera Iyer leads a solar lab in Pune. She won the Kaveri Prize.", "", False),
    ("Raj leads the lab. His work is on batteries.", "I lead a battery lab", False),
    ("Meera Iyer leads a solar lab in Pune and won the Kaveri Prize.", "", True),
    ("Alex leads a lab. They won a prize.", "", True),
    ("Meera leads a lab. She won a prize.", "my pronouns are she/her", True),
    ("Raj leads a lab. He won a prize.", "I use he/him", True),
    ("The Hermitage trust shelters hens in Shere.", "", True),  # words that merely contain he/her are fine
])
def test_gendered_bios_are_kept_only_when_the_person_stated_pronouns(bio, said, keep):
    assert (bio_without_guessed_gender(bio, said) == bio) is keep
