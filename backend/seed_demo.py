from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Assignment,
    AssignmentCategory,
    AssignmentStatus,
    AssignmentTarget,
    AssignmentTargetStatus,
    AttendanceExcuse,
    AttendanceRecord,
    AttendanceStatus,
    CalendarEvent,
    CalendarEventType,
    CurriculumLesson,
    CurriculumPackage,
    CurriculumUnit,
    Family,
    FamilyMembership,
    FamilyRole,
    FamilySettings,
    Grade,
    GradeCategory,
    GradeScale,
    GradedBy,
    GradingPeriod,
    SchoolYear,
    Student,
    Subject,
    SubjectGradingMode,
    Submission,
    Term,
    TermType,
    User,
    UserPreference,
)
from backend.security import hash_password, normalize_email
from backend.services.gradebook import (
    DEFAULT_GRADE_SCALE_NAME,
    DEFAULT_GRADE_SCALE_RANGES,
    build_default_grade_categories,
    map_percent_to_grade,
)
from backend.services.preferences import DEFAULT_USER_PREFERENCES

logger = logging.getLogger(__name__)

SCHOOL_YEAR_NAME = '2025-2026'
SCHOOL_YEAR_START = date(2025, 8, 11)
SCHOOL_YEAR_END = date(2026, 5, 22)
DEMO_EMAIL = 'demo@example.com'
DEMO_PASSWORD = 'demo1234'


@dataclass(frozen=True)
class StudentSpec:
    name: str
    grade: str
    subject_titles: tuple[str, ...]


def _unit(name: str, lessons: list[str], standards: list[str], description: str) -> dict[str, Any]:
    return {
        'name': name,
        'description': description,
        'standards_tags': standards,
        'lessons': [{'name': lesson} for lesson in lessons],
    }


STUDENT_SPECS: tuple[StudentSpec, ...] = (
    StudentSpec(
        'Kindy Kindergartener',
        'K',
        ('English Language Arts', 'Mathematics', 'Science', 'Social Studies', 'Art', 'Music', 'Physical Education'),
    ),
    StudentSpec(
        'Filly Firster',
        '1',
        ('English Language Arts', 'Mathematics', 'Science', 'Social Studies', 'Art', 'Music', 'Physical Education'),
    ),
    StudentSpec(
        'Seiko Seconder',
        '2',
        ('English Language Arts', 'Mathematics', 'Science', 'Social Studies', 'Art', 'Music', 'Physical Education'),
    ),
    StudentSpec(
        'Trey Thirder',
        '3',
        ('English Language Arts', 'Mathematics', 'Science', 'Social Studies', 'Art', 'Music', 'Physical Education'),
    ),
    StudentSpec(
        'Forte Fourther',
        '4',
        ('English Language Arts', 'Mathematics', 'Science', 'Social Studies', 'Art', 'Music', 'Physical Education'),
    ),
    StudentSpec(
        'Fianna Fifther',
        '5',
        ('English Language Arts', 'Mathematics', 'Science', 'Social Studies', 'Art', 'Music', 'Physical Education'),
    ),
    StudentSpec(
        'Sixy Sixther',
        '6',
        ('English Language Arts', 'Mathematics', 'Science', 'Social Studies', 'Art', 'Music', 'Physical Education', 'Health'),
    ),
    StudentSpec(
        'Sevi Seventher',
        '7',
        ('English Language Arts', 'Mathematics', 'Science', 'Social Studies', 'Art', 'Music', 'Physical Education', 'Health'),
    ),
    StudentSpec(
        'Octavia Eighther',
        '8',
        ('English Language Arts', 'Mathematics', 'Science', 'Social Studies', 'Art', 'Music', 'Physical Education', 'Health'),
    ),
    StudentSpec(
        'Nina Ninther',
        '9',
        ('English I', 'Algebra I', 'Physical Science', 'Oklahoma History', 'Fine Arts', 'Physical Education', 'Health', 'Introduction to Computer Science'),
    ),
    StudentSpec(
        'Dex Tenther',
        '10',
        ('English II', 'Geometry', 'Biology', 'World History', 'Fine Arts', 'Physical Education', 'Health', 'Spanish I'),
    ),
    StudentSpec(
        'Elle Eleventher',
        '11',
        ('English III', 'Algebra II', 'Chemistry', 'US History', 'Fine Arts', 'Physical Education', 'Health', 'Personal Finance'),
    ),
    StudentSpec(
        'Twyla Twelfther',
        '12',
        ('English IV', 'Pre-Calculus & Statistics', 'Environmental Science', 'Government & Economics', 'Fine Arts', 'Physical Education', 'Health', 'Psychology'),
    ),
)

CURRICULUM_MAP: dict[str, dict[str, list[dict[str, Any]]]] = {
    'K': {
        'English Language Arts': [
            _unit(
                'Letter Recognition & Phonics',
                ['Uppercase Letters', 'Lowercase Letters', 'Letter Sounds A-M', 'Letter Sounds N-Z', 'Rhyming Words', 'Syllable Clapping'],
                ['OAS.ELA.K.PA.1', 'OAS.ELA.K.PA.2'],
                'Oklahoma kindergarten ELA foundations with phonological awareness and early decoding.',
            ),
            _unit(
                'Reading Readiness',
                ['Print Concepts', 'Story Elements', 'Reading Aloud', 'Sight Words Set 1'],
                ['OAS.ELA.K.R.1', 'OAS.ELA.K.R.2'],
                'Build print awareness, comprehension, and speaking about text.',
            ),
            _unit(
                'Writing Foundations',
                ['Pencil Grip & Tracing', 'Writing First Name', 'Drawing Stories', 'Simple Sentences'],
                ['OAS.ELA.K.W.1', 'OAS.ELA.K.W.2'],
                'Practice fine-motor writing routines and composing simple ideas.',
            ),
        ],
        'Mathematics': [
            _unit(
                'Counting & Cardinality',
                ['Counting to 20', 'Number Recognition', 'One-to-One Correspondence', 'Comparing Numbers'],
                ['OAS.Math.K.N.1', 'OAS.Math.K.N.2'],
                'Early number sense aligned to Oklahoma kindergarten expectations.',
            ),
            _unit(
                'Operations',
                ['Addition Within 5', 'Subtraction Within 5', 'Word Problems', 'Making 10 with Counters'],
                ['OAS.Math.K.A.1', 'OAS.Math.K.A.2'],
                'Concrete models for joining and separating sets.',
            ),
            _unit(
                'Geometry & Measurement',
                ['Shapes', 'Positional Words', 'Sorting & Classifying', 'Longer and Shorter'],
                ['OAS.Math.K.G.1', 'OAS.Math.K.M.1'],
                'Use shape and measurement language in hands-on investigations.',
            ),
        ],
        'Science': [
            _unit(
                'Living Things Around Us',
                ['Plant Needs', 'Animal Needs', 'Weather and Seasons', 'Habitats'],
                ['OAS.SCI.K.LS1.1', 'OAS.SCI.K.ESS2.1'],
                'Observe patterns in plants, animals, and seasonal change.',
            ),
            _unit(
                'Motion & Materials',
                ['Pushes and Pulls', 'Ramps and Rolls', 'Strong and Weak Forces', 'Solid or Liquid'],
                ['OAS.SCI.K.PS2.1', 'OAS.SCI.K.PS1.1'],
                'Investigate motion and properties with classroom materials.',
            ),
            _unit(
                'Science Practices',
                ['Asking Questions', 'Recording Observations', 'Comparing Data', 'Sharing Findings'],
                ['OAS.SCI.K.SE.1', 'OAS.SCI.K.SE.2'],
                'Practice Oklahoma science and engineering habits for young learners.',
            ),
        ],
        'Social Studies': [
            _unit(
                'My School & Community',
                ['Classroom Rules', 'Community Helpers', 'Maps of Our School', 'Goods and Services'],
                ['OAS.SS.K.1', 'OAS.SS.K.2'],
                'Introduce citizenship, geography, and economics through the local community.',
            ),
            _unit(
                'Symbols & Traditions',
                ['American Flag', 'State Symbols', 'Family Traditions', 'National Holidays'],
                ['OAS.SS.K.3', 'OAS.SS.K.4'],
                'Explore shared traditions and important civic symbols.',
            ),
            _unit(
                'Then & Now',
                ['Past and Present', 'Timelines', 'Leaders in Our Community', 'Working Together'],
                ['OAS.SS.K.5', 'OAS.SS.K.6'],
                'Use simple timelines and stories to compare past and present.',
            ),
        ],
    },
    '1': {
        'English Language Arts': [
            _unit('Phonics & Word Study', ['Short Vowels', 'Long Vowels', 'Consonant Blends', 'High-Frequency Words'], ['OAS.ELA.1.PA.1', 'OAS.ELA.1.PA.2'], 'First-grade decoding and phonics patterns.'),
            _unit('Reading for Meaning', ['Main Idea', 'Story Sequence', 'Ask and Answer Questions', 'Compare Characters'], ['OAS.ELA.1.R.1', 'OAS.ELA.1.R.2'], 'Build literal comprehension and retell fluency.'),
            _unit('Writing & Speaking', ['Opinion Sentences', 'Informational Facts', 'Narrative Beginnings', 'Speaking in Complete Sentences'], ['OAS.ELA.1.W.1', 'OAS.ELA.1.W.2'], 'Compose complete ideas with drawing, dictation, and writing.'),
        ],
        'Mathematics': [
            _unit('Place Value to 120', ['Counting to 120', 'Tens and Ones', 'Compare Numbers', 'Skip Counting'], ['OAS.Math.1.N.1', 'OAS.Math.1.N.2'], 'Understand two-digit numbers and patterns.'),
            _unit('Addition & Subtraction', ['Facts Within 10', 'Make a Ten', 'Related Facts', 'Story Problems'], ['OAS.Math.1.A.1', 'OAS.Math.1.A.2'], 'Use strategies to solve and explain addition and subtraction.'),
            _unit('Shapes & Measurement', ['2D Shapes', '3D Shapes', 'Length in Units', 'Time to the Hour'], ['OAS.Math.1.G.1', 'OAS.Math.1.M.1'], 'Describe shapes and measure with nonstandard and standard units.'),
        ],
        'Science': [
            _unit('Patterns in Nature', ['Day and Night', 'Seasonal Weather', 'Plant Life Cycles', 'Animal Behaviors'], ['OAS.SCI.1.ESS1.1', 'OAS.SCI.1.LS1.1'], 'Observe predictable patterns in the sky and living things.'),
            _unit('Light and Sound', ['Sources of Light', 'Seeing Objects', 'Vibrations', 'Communicating with Sound'], ['OAS.SCI.1.PS4.1', 'OAS.SCI.1.PS4.2'], 'Discover how light and sound help us interact with the world.'),
            _unit('Engineering Design', ['Ask a Problem', 'Build a Shelter', 'Test a Solution', 'Improve the Design'], ['OAS.SCI.1.ETS1.1', 'OAS.SCI.1.ETS1.2'], 'Apply simple design thinking to classroom challenges.'),
        ],
        'Social Studies': [
            _unit('Citizenship Basics', ['Rules and Laws', 'Good Citizens', 'Respecting Others', 'Leaders at School'], ['OAS.SS.1.1', 'OAS.SS.1.2'], 'Practice first-grade citizenship and responsibility.'),
            _unit('Geography of Home', ['Maps and Globes', 'Land and Water', 'Urban and Rural', 'Weather and Places'], ['OAS.SS.1.3', 'OAS.SS.1.4'], 'Use maps and place features to describe communities.'),
            _unit('Economics & History', ['Needs and Wants', 'Jobs People Do', 'Family Timelines', 'National Stories'], ['OAS.SS.1.5', 'OAS.SS.1.6'], 'Connect family history and basic economics to everyday life.'),
        ],
    },
    '2': {
        'English Language Arts': [
            _unit('Word Analysis & Fluency', ['Open and Closed Syllables', 'Prefixes and Suffixes', 'Context Clues', 'Fluent Reading'], ['OAS.ELA.2.PA.1', 'OAS.ELA.2.R.2'], 'Second-grade word study and reading fluency practice.'),
            _unit('Reading Literature & Info Text', ['Text Features', 'Character Traits', 'Cause and Effect', 'Author Purpose'], ['OAS.ELA.2.R.1', 'OAS.ELA.2.R.3'], 'Compare stories and informational texts using evidence.'),
            _unit('Writing Workshop', ['Paragraph Basics', 'Opinion Reasons', 'Research Notes', 'Oral Presentations'], ['OAS.ELA.2.W.1', 'OAS.ELA.2.W.2'], 'Write organized responses and share findings clearly.'),
        ],
        'Mathematics': [
            _unit('Place Value to 1,000', ['Hundreds Tens Ones', 'Expanded Form', 'Compare Three-Digit Numbers', 'Number Lines'], ['OAS.Math.2.N.1', 'OAS.Math.2.N.2'], 'Use place value models and comparisons through 1,000.'),
            _unit('Add, Subtract, Solve', ['Two-Digit Addition', 'Regrouping', 'Two-Digit Subtraction', 'Multi-Step Word Problems'], ['OAS.Math.2.A.1', 'OAS.Math.2.A.2'], 'Develop efficient strategies for two-digit operations.'),
            _unit('Measurement & Data', ['Money', 'Time to 5 Minutes', 'Line Plots', 'Fractions as Shapes'], ['OAS.Math.2.M.1', 'OAS.Math.2.D.1'], 'Solve measurement and data questions with real-world contexts.'),
        ],
        'Science': [
            _unit('Earth Systems', ['Slow and Fast Changes', 'Landforms', 'Water on Earth', 'Natural Resources'], ['OAS.SCI.2.ESS1.1', 'OAS.SCI.2.ESS2.1'], 'Explore Earth changes and the role of water.'),
            _unit('Plants, Animals & Pollination', ['Plant Structures', 'Seed Dispersal', 'Pollinators', 'Habitats'], ['OAS.SCI.2.LS2.1', 'OAS.SCI.2.LS2.2'], 'Connect plant and animal structures to survival.'),
            _unit('Matter & Motion', ['Heating and Cooling', 'States of Matter', 'Forces and Motion', 'Design a Device'], ['OAS.SCI.2.PS1.1', 'OAS.SCI.2.ETS1.1'], 'Investigate material changes and motion through models.'),
        ],
        'Social Studies': [
            _unit('Oklahoma Communities', ['Rural Communities', 'Urban Communities', 'Community Services', 'Producers and Consumers'], ['OAS.SS.2.1', 'OAS.SS.2.2'], 'Study Oklahoma communities and local economics.'),
            _unit('Maps and Regions', ['Cardinal Directions', 'Map Keys', 'Regions of Oklahoma', 'Transportation'], ['OAS.SS.2.3', 'OAS.SS.2.4'], 'Use geographic tools to describe Oklahoma places.'),
            _unit('History Through Stories', ['Historic Oklahomans', 'Cherokee Traditions', 'Timelines', 'Celebrations'], ['OAS.SS.2.5', 'OAS.SS.2.6'], 'Build early Oklahoma history knowledge through stories and timelines.'),
        ],
    },
    '3': {
        'English Language Arts': [
            _unit('Reading Strategies', ['Theme and Central Idea', 'Summarizing Text', 'Literal vs. Inferential', 'Academic Vocabulary'], ['OAS.ELA.3.R.1', 'OAS.ELA.3.R.2'], 'Read with stronger inference and theme awareness.'),
            _unit('Grammar & Language', ['Nouns and Verbs', 'Subject-Verb Agreement', 'Punctuation Review', 'Using Reference Tools'], ['OAS.ELA.3.G.1', 'OAS.ELA.3.G.2'], 'Apply grade-level conventions and language resources.'),
            _unit('Narrative & Informative Writing', ['Strong Leads', 'Paragraph Unity', 'Research Basics', 'Speaking with Visuals'], ['OAS.ELA.3.W.1', 'OAS.ELA.3.W.2'], 'Write multi-paragraph pieces with evidence and organization.'),
        ],
        'Mathematics': [
            _unit('Multiplication & Division', ['Arrays', 'Equal Groups', 'Related Facts', 'Word Problems'], ['OAS.Math.3.A.1', 'OAS.Math.3.A.2'], 'Introduce multiplication and division with models and stories.'),
            _unit('Fractions & Number Sense', ['Unit Fractions', 'Equivalent Fractions', 'Compare Fractions', 'Place Value to 10,000'], ['OAS.Math.3.N.1', 'OAS.Math.3.N.2'], 'Strengthen fraction sense and larger whole numbers.'),
            _unit('Area, Perimeter & Data', ['Perimeter', 'Area Models', 'Scaled Graphs', 'Elapsed Time'], ['OAS.Math.3.M.1', 'OAS.Math.3.D.1'], 'Solve measurement and graphing problems using models.'),
        ],
        'Science': [
            _unit('Forces & Interactions', ['Balanced and Unbalanced Forces', 'Magnetism', 'Motion Investigation', 'Engineering a Bridge'], ['OAS.SCI.3.PS2.1', 'OAS.SCI.3.ETS1.1'], 'Investigate forces, motion, and simple engineering.'),
            _unit('Life Cycles & Traits', ['Inherited Traits', 'Life Cycles', 'Ecosystems', 'Environmental Changes'], ['OAS.SCI.3.LS3.1', 'OAS.SCI.3.LS4.1'], 'Explore how organisms grow, survive, and respond to change.'),
            _unit('Weather & Climate', ['Weather Data', 'Climate Zones', 'Severe Weather Safety', 'Patterns in the Sky'], ['OAS.SCI.3.ESS2.1', 'OAS.SCI.3.ESS2.2'], 'Use data to describe weather and climate patterns.'),
        ],
        'Social Studies': [
            _unit('Communities & Government', ['Local Government', 'Public Services', 'Taxes and Choices', 'Being an Active Citizen'], ['OAS.SS.3.1', 'OAS.SS.3.2'], 'Learn how governments and economies support communities.'),
            _unit('Geography of Oklahoma', ['Physical Regions', 'Natural Resources', 'Human-Environment Interaction', 'Population Patterns'], ['OAS.SS.3.3', 'OAS.SS.3.4'], 'Analyze Oklahoma geography and settlement patterns.'),
            _unit('History of Oklahoma', ['Indigenous Nations', 'Land Runs', 'Statehood', 'Modern Oklahoma'], ['OAS.SS.3.5', 'OAS.SS.3.6'], 'Build an introductory Oklahoma history timeline.'),
        ],
    },
    '4': {
        'English Language Arts': [
            _unit('Close Reading', ['Theme from Details', 'Point of View', 'Text Evidence', 'Compare Texts'], ['OAS.ELA.4.R.1', 'OAS.ELA.4.R.2'], 'Read closely and cite evidence from literature and information.'),
            _unit('Word Meaning & Grammar', ['Greek and Latin Roots', 'Figurative Language', 'Sentence Structure', 'Capitalization Review'], ['OAS.ELA.4.V.1', 'OAS.ELA.4.G.1'], 'Use vocabulary strategies and conventions accurately.'),
            _unit('Essay Writing', ['Opinion Essays', 'Informational Essays', 'Narrative Elaboration', 'Presentation Skills'], ['OAS.ELA.4.W.1', 'OAS.ELA.4.W.2'], 'Write and present organized pieces with supporting details.'),
        ],
        'Mathematics': [
            _unit('Multi-Digit Operations', ['Place Value to Millions', 'Multi-Digit Multiplication', 'Long Division Basics', 'Estimation'], ['OAS.Math.4.N.1', 'OAS.Math.4.A.1'], 'Use place value and operations to solve larger number problems.'),
            _unit('Fractions & Decimals', ['Equivalent Fractions', 'Mixed Numbers', 'Decimal Tenths and Hundredths', 'Compare Decimals'], ['OAS.Math.4.N.2', 'OAS.Math.4.N.3'], 'Connect fraction concepts to decimal notation.'),
            _unit('Geometry & Measurement', ['Angles', 'Classify Shapes', 'Area and Perimeter', 'Line Plots with Fractions'], ['OAS.Math.4.G.1', 'OAS.Math.4.M.1'], 'Measure, classify, and represent data precisely.'),
        ],
        'Science': [
            _unit('Energy Transfer', ['Electricity Basics', 'Sound Energy', 'Light Reflection', 'Energy from Food'], ['OAS.SCI.4.PS3.1', 'OAS.SCI.4.PS4.1'], 'Trace how energy moves through systems and signals.'),
            _unit('Earth Processes', ['Rocks and Minerals', 'Fossils', 'Weathering and Erosion', 'Natural Hazards'], ['OAS.SCI.4.ESS1.1', 'OAS.SCI.4.ESS2.1'], 'Investigate Earth materials and processes over time.'),
            _unit('Structures & Function', ['Internal and External Structures', 'Animal Senses', 'Plant Responses', 'Designing Solutions'], ['OAS.SCI.4.LS1.1', 'OAS.SCI.4.ETS1.1'], 'Connect structures to survival and engineering ideas.'),
        ],
        'Social Studies': [
            _unit('Native Oklahoma', ['Tribal Nations', 'Cultural Regions', 'Sovereignty', 'Primary Sources'], ['OAS.SS.4.1', 'OAS.SS.4.2'], 'Study tribal nations and Oklahoma civic identity.'),
            _unit('State History', ['Territories', 'Land Rushes', 'Oil Boom', 'Government of Oklahoma'], ['OAS.SS.4.3', 'OAS.SS.4.4'], 'Examine major events in Oklahoma history and government.'),
            _unit('Economics & Geography', ['Trade in Oklahoma', 'Agriculture', 'Population Shifts', 'Regions Review'], ['OAS.SS.4.5', 'OAS.SS.4.6'], 'Connect Oklahoma geography to economy and migration.'),
        ],
    },
    '5': {
        'English Language Arts': [
            _unit('Analyzing Text', ['Theme Across Texts', 'Author Craft', 'Summarize and Paraphrase', 'Integrating Information'], ['OAS.ELA.5.R.1', 'OAS.ELA.5.R.2'], 'Use evidence to analyze increasingly complex text.'),
            _unit('Language & Vocabulary', ['Context and Connotation', 'Parts of Speech Review', 'Complex Sentences', 'Domain Vocabulary'], ['OAS.ELA.5.V.1', 'OAS.ELA.5.G.1'], 'Strengthen precise language and grammar choices.'),
            _unit('Writing from Sources', ['Argument Writing', 'Informative Essays', 'Narrative Revision', 'Collaborative Discussions'], ['OAS.ELA.5.W.1', 'OAS.ELA.5.W.2'], 'Draft and revise writing that uses research and evidence.'),
        ],
        'Mathematics': [
            _unit('Operations with Decimals', ['Place Value Through Thousandths', 'Add and Subtract Decimals', 'Multiply Decimals', 'Divide Whole Numbers'], ['OAS.Math.5.N.1', 'OAS.Math.5.A.1'], 'Work flexibly with decimals and whole-number operations.'),
            _unit('Fraction Computation', ['Add Fractions', 'Subtract Fractions', 'Multiply Fractions', 'Real-World Fraction Problems'], ['OAS.Math.5.N.2', 'OAS.Math.5.N.3'], 'Model and solve fraction computations.'),
            _unit('Volume & Coordinate Graphing', ['Volume of Prisms', 'Coordinate Plane', 'Data Patterns', 'Measurement Conversions'], ['OAS.Math.5.M.1', 'OAS.Math.5.G.1'], 'Apply geometry and measurement in authentic tasks.'),
        ],
        'Science': [
            _unit('Matter & Its Interactions', ['Particle Model', 'Conservation of Matter', 'Mixtures and Solutions', 'Chemical Reactions'], ['OAS.SCI.5.PS1.1', 'OAS.SCI.5.PS1.2'], 'Understand matter through observations and models.'),
            _unit('Earth & Space Systems', ['Water Cycle', 'Weather Tools', 'Earth-Sun-Moon', 'Stars and Galaxies'], ['OAS.SCI.5.ESS1.1', 'OAS.SCI.5.ESS2.1'], 'Explain Earth and space patterns using data.'),
            _unit('Ecosystems & Engineering', ['Food Webs', 'Environmental Change', 'Human Impact', 'Design a Water Filter'], ['OAS.SCI.5.LS2.1', 'OAS.SCI.5.ETS1.1'], 'Analyze ecosystems and design to solve problems.'),
        ],
        'Social Studies': [
            _unit('Foundations of the United States', ['Colonial America', 'Road to Revolution', 'Declaration of Independence', 'Constitution Basics'], ['OAS.SS.5.1', 'OAS.SS.5.2'], 'Trace the founding of the United States.'),
            _unit('Westward Expansion & Conflict', ['Louisiana Purchase', 'Trail of Tears', 'Civil War Causes', 'Reconstruction'], ['OAS.SS.5.3', 'OAS.SS.5.4'], 'Study growth, conflict, and major turning points.'),
            _unit('Geography, Economy & Civics', ['Regions of the US', 'Free Enterprise', 'Branches of Government', 'Rights and Responsibilities'], ['OAS.SS.5.5', 'OAS.SS.5.6'], 'Connect US geography, economics, and citizenship.'),
        ],
    },
    '6': {
        'English Language Arts': [
            _unit('Reading Like a Scholar', ['Annotating Text', 'Claim and Evidence', 'Theme Development', 'Comparing Authors'], ['OAS.ELA.6.R.1', 'OAS.ELA.6.R.2'], 'Sixth-grade Oklahoma reading analysis using text evidence.'),
            _unit('Language & Vocabulary', ['Word Origins', 'Sentence Variety', 'Connotation', 'Academic Discussion'], ['OAS.ELA.6.V.1', 'OAS.ELA.6.G.1'], 'Develop precision in speaking and writing.'),
            _unit('Narrative, Informative, Argument', ['Narrative Techniques', 'Informational Structure', 'Argument Claims', 'Research Citations'], ['OAS.ELA.6.W.1', 'OAS.ELA.6.W.2'], 'Write across genres with evidence and organization.'),
        ],
        'Mathematics': [
            _unit('Ratios & Expressions', ['Ratio Language', 'Unit Rate', 'Equivalent Expressions', 'Distributive Property'], ['OAS.Math.6.A.1', 'OAS.Math.6.A.2'], 'Build proportional thinking and algebra foundations.'),
            _unit('Fractions, Decimals & Integers', ['Divide Fractions', 'Decimal Operations', 'Integer Number Line', 'Coordinate Plane'], ['OAS.Math.6.N.1', 'OAS.Math.6.N.2'], 'Extend number system understanding.'),
            _unit('Statistics & Geometry', ['Statistical Questions', 'Center and Variability', 'Area and Surface Area', 'Volume'], ['OAS.Math.6.D.1', 'OAS.Math.6.G.1'], 'Analyze data and solve geometry problems.'),
        ],
        'Science': [
            _unit('Earth Systems', ['Plate Tectonics', 'Rock Cycle', 'Water Resources', 'Weather Patterns'], ['OAS.SCI.6.ESS2.1', 'OAS.SCI.6.ESS2.2'], 'Investigate Earth systems and interactions.'),
            _unit('Cells to Ecosystems', ['Cell Theory', 'Body Systems', 'Ecosystem Relationships', 'Biodiversity'], ['OAS.SCI.6.LS1.1', 'OAS.SCI.6.LS2.1'], 'Connect structures, systems, and ecosystems.'),
            _unit('Scientific Practices', ['Planning Investigations', 'Graphing Data', 'CER Writing', 'Engineering Constraints'], ['OAS.SCI.6.SE.1', 'OAS.SCI.6.ETS1.1'], 'Use Oklahoma science practices to explain phenomena.'),
        ],
        'Social Studies': [
            _unit('Ancient Civilizations', ['Mesopotamia', 'Egypt', 'India', 'China'], ['OAS.SS.6.1', 'OAS.SS.6.2'], 'Survey early civilizations through geography and culture.'),
            _unit('Classical World', ['Greece', 'Rome', 'World Religions', 'Cultural Diffusion'], ['OAS.SS.6.3', 'OAS.SS.6.4'], 'Study classical civilizations and their lasting influence.'),
            _unit('Geography Skills', ['Reading Maps', 'Regions and Climate', 'Human Migration', 'Economic Systems'], ['OAS.SS.6.5', 'OAS.SS.6.6'], 'Use geography to explain movement and development.'),
        ],
    },
    '7': {
        'English Language Arts': [
            _unit('Critical Reading', ['Author Perspective', 'Text Structures', 'Supporting Claims', 'Media Analysis'], ['OAS.ELA.7.R.1', 'OAS.ELA.7.R.2'], 'Analyze complex texts and media across formats.'),
            _unit('Language Craft', ['Precise Vocabulary', 'Phrases and Clauses', 'Transitions', 'Collaborative Discussion'], ['OAS.ELA.7.V.1', 'OAS.ELA.7.G.1'], 'Strengthen syntax and academic conversation.'),
            _unit('Writing with Evidence', ['Narrative Point of View', 'Research Writing', 'Argument Counterclaims', 'Revision Workshops'], ['OAS.ELA.7.W.1', 'OAS.ELA.7.W.2'], 'Compose polished pieces rooted in evidence.'),
        ],
        'Mathematics': [
            _unit('Proportional Relationships', ['Constant of Proportionality', 'Percents', 'Scale Drawings', 'Simple Interest'], ['OAS.Math.7.A.1', 'OAS.Math.7.A.2'], 'Apply proportional reasoning in real contexts.'),
            _unit('Expressions & Equations', ['Integer Operations', 'Solve Two-Step Equations', 'Inequalities', 'Angle Relationships'], ['OAS.Math.7.N.1', 'OAS.Math.7.A.3'], 'Solve equations and reason with geometric relationships.'),
            _unit('Probability & Statistics', ['Chance Experiments', 'Probability Models', 'Comparing Samples', 'Circle Geometry'], ['OAS.Math.7.D.1', 'OAS.Math.7.G.1'], 'Use data and probability to make predictions.'),
        ],
        'Science': [
            _unit('Chemical Reactions', ['Atomic Structure', 'Periodic Table', 'Evidence of Reactions', 'Conservation of Mass'], ['OAS.SCI.7.PS1.1', 'OAS.SCI.7.PS1.2'], 'Investigate matter and chemical change.'),
            _unit('Ecosystem Dynamics', ['Photosynthesis', 'Food Web Stability', 'Populations', 'Human Impact'], ['OAS.SCI.7.LS1.1', 'OAS.SCI.7.LS2.1'], 'Explain ecosystem interactions and sustainability.'),
            _unit('Earth History', ['Geologic Time', 'Fossils', 'Natural Hazards', 'Resource Management'], ['OAS.SCI.7.ESS1.1', 'OAS.SCI.7.ESS3.1'], 'Connect Earth history to modern environmental decisions.'),
        ],
        'Social Studies': [
            _unit('Geography & World Regions', ['Physical Geography', 'Population Patterns', 'Culture Regions', 'Global Interdependence'], ['OAS.SS.7.1', 'OAS.SS.7.2'], 'Use geographic lenses to study the modern world.'),
            _unit('Civics & Economics', ['Governments Around the World', 'Economic Systems', 'Trade', 'Human Rights'], ['OAS.SS.7.3', 'OAS.SS.7.4'], 'Compare political and economic systems globally.'),
            _unit('Contemporary Issues', ['Migration', 'Conflict and Cooperation', 'Technology', 'Sustainable Development'], ['OAS.SS.7.5', 'OAS.SS.7.6'], 'Discuss global issues using evidence and maps.'),
        ],
    },
    '8': {
        'English Language Arts': [
            _unit('Sophisticated Text Analysis', ['Analyzing Theme', 'Rhetorical Appeals', 'Counterargument', 'Synthesis of Sources'], ['OAS.ELA.8.R.1', 'OAS.ELA.8.R.2'], 'Interpret increasingly complex literary and informational texts.'),
            _unit('Language for Impact', ['Tone and Mood', 'Verbals', 'Parallel Structure', 'Vocabulary in Context'], ['OAS.ELA.8.V.1', 'OAS.ELA.8.G.1'], 'Refine grammar and style for intentional communication.'),
            _unit('Research & Composition', ['Narrative Pacing', 'Informative Explanations', 'Argument Essays', 'Formal Presentations'], ['OAS.ELA.8.W.1', 'OAS.ELA.8.W.2'], 'Compose and present research-backed writing.'),
        ],
        'Mathematics': [
            _unit('Linear Relationships', ['Slope as Rate of Change', 'Graphing Lines', 'Write Equations', 'Systems Preview'], ['OAS.Math.8.A.1', 'OAS.Math.8.A.2'], 'Connect tables, graphs, and equations for linear models.'),
            _unit('Functions & Exponents', ['Function Inputs and Outputs', 'Compare Functions', 'Integer Exponents', 'Scientific Notation'], ['OAS.Math.8.F.1', 'OAS.Math.8.N.1'], 'Use function thinking and exponent rules.'),
            _unit('Geometry & Data', ['Transformations', 'Pythagorean Theorem', 'Volume of Cylinders', 'Scatter Plots'], ['OAS.Math.8.G.1', 'OAS.Math.8.D.1'], 'Solve geometric and statistical problems with precision.'),
        ],
        'Science': [
            _unit('Forces & Motion', ['Newton Laws', 'Speed and Velocity', 'Momentum', 'Engineering a Safety Device'], ['OAS.SCI.8.PS2.1', 'OAS.SCI.8.ETS1.1'], 'Apply forces and motion ideas to engineering design.'),
            _unit('Waves & Information', ['Wave Properties', 'Sound and Light', 'Digital Signals', 'Communication Systems'], ['OAS.SCI.8.PS4.1', 'OAS.SCI.8.PS4.2'], 'Explain how waves transfer energy and information.'),
            _unit('Space Systems', ['Earth-Moon-Sun', 'Seasons and Eclipses', 'Gravity', 'Universe Scale'], ['OAS.SCI.8.ESS1.1', 'OAS.SCI.8.ESS1.2'], 'Model space systems and observable patterns.'),
        ],
        'Social Studies': [
            _unit('Early America', ['Colonization', 'Revolution', 'Constitution', 'New Republic'], ['OAS.SS.8.1', 'OAS.SS.8.2'], 'Follow the growth of the United States from colonies to republic.'),
            _unit('Expansion & Reform', ['Jacksonian Era', 'Manifest Destiny', 'Reform Movements', 'Sectionalism'], ['OAS.SS.8.3', 'OAS.SS.8.4'], 'Examine growth, reform, and rising sectional tensions.'),
            _unit('Civil War & Reconstruction', ['Causes of War', 'Major Battles', 'Reconstruction Plans', 'Legacy of the Era'], ['OAS.SS.8.5', 'OAS.SS.8.6'], 'Study the Civil War and its long-term consequences.'),
        ],
    },
    '9': {
        'English I': [
            _unit('Narrative & Short Fiction', ['Plot and Structure', 'Characterization', 'Theme Development', 'Narrative Writing'], ['OAS.ELA.9.R.1', 'OAS.ELA.9.W.1'], 'Analyze narrative texts and craft original narratives.'),
            _unit('Informational & Argument Text', ['Evaluating Claims', 'Text Features', 'Rhetorical Appeals', 'Argument Essay'], ['OAS.ELA.9.R.2', 'OAS.ELA.9.W.2'], 'Read and write arguments grounded in evidence.'),
            _unit('Language, Research & Speech', ['Grammar for Style', 'Research Process', 'Source Credibility', 'Formal Presentation'], ['OAS.ELA.9.G.1', 'OAS.ELA.9.W.3'], 'Use standard English and research skills in presentations.'),
        ],
        'Algebra I': [
            _unit('Linear Equations & Inequalities', ['Solve Multi-Step Equations', 'Graph Inequalities', 'Model with Functions', 'Interpret Slope'], ['OAS.A1.A.1', 'OAS.A1.F.1'], 'Build algebra fluency with linear relationships.'),
            _unit('Systems & Exponents', ['Solve Systems Graphically', 'Solve Systems Algebraically', 'Exponent Rules', 'Scientific Notation'], ['OAS.A1.A.2', 'OAS.A1.N.1'], 'Apply algebraic methods to systems and exponents.'),
            _unit('Quadratics & Statistics', ['Intro to Quadratics', 'Factoring', 'Data Displays', 'Regression Basics'], ['OAS.A1.F.2', 'OAS.A1.D.1'], 'Connect quadratic models and introductory statistics.'),
        ],
        'Physical Science': [
            _unit('Matter & Atomic Theory', ['Atomic Structure', 'Periodic Trends', 'Chemical Bonding', 'Reactions'], ['OAS.PS.PS1.1', 'OAS.PS.PS1.2'], 'Study matter from atoms to chemical change.'),
            _unit('Forces & Energy', ['Newton Laws', 'Work and Power', 'Energy Transformations', 'Thermal Systems'], ['OAS.PS.PS2.1', 'OAS.PS.PS3.1'], 'Explain motion and energy in physical systems.'),
            _unit('Waves & Technology', ['Wave Behavior', 'Electromagnetic Spectrum', 'Circuits', 'Engineering Design'], ['OAS.PS.PS4.1', 'OAS.PS.ETS1.1'], 'Connect waves and electricity to modern technology.'),
        ],
        'Oklahoma History': [
            _unit('Indigenous Oklahoma', ['Tribal Homelands', 'Removal and Resettlement', 'Sovereignty', 'Primary Sources'], ['OAS.OKH.1', 'OAS.OKH.2'], 'Center Oklahoma history on tribal nations and sovereignty.'),
            _unit('Territory to Statehood', ['Land Runs', 'Allotment', 'State Constitution', 'Early Statehood'], ['OAS.OKH.3', 'OAS.OKH.4'], 'Trace key statehood events and institutions.'),
            _unit('Modern Oklahoma', ['Oil and Agriculture', 'Civil Rights in Oklahoma', 'Economic Development', 'Current Issues'], ['OAS.OKH.5', 'OAS.OKH.6'], 'Analyze Oklahoma in the twentieth century and today.'),
        ],
    },
    '10': {
        'English II': [
            _unit('World Literature', ['Epic Traditions', 'Drama Analysis', 'Poetic Devices', 'Literary Comparison'], ['OAS.ELA.10.R.1', 'OAS.ELA.10.R.2'], 'Study world literature with close reading and comparison.'),
            _unit('Informative & Argument Writing', ['Explanatory Structure', 'Research Integration', 'Counterclaims', 'Revision for Clarity'], ['OAS.ELA.10.W.1', 'OAS.ELA.10.W.2'], 'Write clear, well-supported informative and argument pieces.'),
            _unit('Language & Communication', ['Syntax for Effect', 'Vocabulary Precision', 'Seminar Discussion', 'Speech Delivery'], ['OAS.ELA.10.G.1', 'OAS.ELA.10.SL.1'], 'Refine language choices and presentation skills.'),
        ],
        'Geometry': [
            _unit('Reasoning with Figures', ['Points Lines and Planes', 'Angle Relationships', 'Proof Strategies', 'Triangle Congruence'], ['OAS.G.1', 'OAS.G.2'], 'Develop logical geometric reasoning and proof.'),
            _unit('Similarity & Transformations', ['Dilations', 'Similarity', 'Right Triangle Trig Intro', 'Coordinate Geometry'], ['OAS.G.3', 'OAS.G.4'], 'Model similarity, transformations, and trigonometric ratios.'),
            _unit('Measurement & Circles', ['Area and Volume', 'Circle Theorems', 'Probability Models', 'Statistics Review'], ['OAS.G.5', 'OAS.G.6'], 'Apply geometry to measurement, circles, and probability.'),
        ],
        'Biology': [
            _unit('Cells & Genetics', ['Cell Structure', 'Cellular Transport', 'DNA and Genes', 'Mitosis and Meiosis'], ['OAS.BIO.LS1.1', 'OAS.BIO.LS3.1'], 'Connect cell processes to heredity and life functions.'),
            _unit('Evolution & Ecology', ['Natural Selection', 'Evidence for Evolution', 'Population Dynamics', 'Energy Flow'], ['OAS.BIO.LS4.1', 'OAS.BIO.LS2.1'], 'Explain biodiversity and ecosystem relationships.'),
            _unit('Scientific Inquiry in Biology', ['Experimental Design', 'Analyzing Data', 'Bioethics', 'Environmental Stewardship'], ['OAS.BIO.SE.1', 'OAS.BIO.ETS1.1'], 'Use evidence-based reasoning in biological contexts.'),
        ],
        'World History': [
            _unit('Global Transformations', ['Renaissance', 'Reformation', 'Age of Exploration', 'Scientific Revolution'], ['OAS.WH.1', 'OAS.WH.2'], 'Trace early modern global change and exchange.'),
            _unit('Revolutions & Industry', ['American and French Revolutions', 'Industrial Revolution', 'Imperialism', 'Nationalism'], ['OAS.WH.3', 'OAS.WH.4'], 'Examine political and economic transformations.'),
            _unit('The Modern Era', ['World Wars', 'Cold War', 'Decolonization', 'Globalization'], ['OAS.WH.5', 'OAS.WH.6'], 'Study the forces shaping the modern world.'),
        ],
    },
    '11': {
        'English III': [
            _unit('American Literature', ['Founding Texts', 'Romanticism', 'Realism', 'Modern Voices'], ['OAS.ELA.11.R.1', 'OAS.ELA.11.R.2'], 'Analyze major movements in American literature.'),
            _unit('Rhetoric & Argument', ['Analyzing Speeches', 'Synthesis Essay', 'Research and Citation', 'Media Literacy'], ['OAS.ELA.11.W.1', 'OAS.ELA.11.W.2'], 'Write sophisticated arguments using multiple sources.'),
            _unit('Language & Presentation', ['Diction and Tone', 'Sentence Variety', 'Seminar Leadership', 'Multimedia Presentation'], ['OAS.ELA.11.G.1', 'OAS.ELA.11.SL.1'], 'Use strong style and presentation strategies for authentic audiences.'),
        ],
        'Algebra II': [
            _unit('Functions & Complex Numbers', ['Quadratic Functions', 'Polynomial Operations', 'Complex Numbers', 'Function Transformations'], ['OAS.A2.F.1', 'OAS.A2.N.1'], 'Extend function work to higher-order expressions.'),
            _unit('Exponential & Logarithmic Models', ['Growth and Decay', 'Exponential Equations', 'Logarithms', 'Recursive Models'], ['OAS.A2.F.2', 'OAS.A2.A.1'], 'Model real-world change with advanced functions.'),
            _unit('Statistics & Trigonometry', ['Normal Distributions', 'Inference Basics', 'Trigonometric Functions', 'Modeling Projects'], ['OAS.A2.D.1', 'OAS.A2.T.1'], 'Blend data analysis with trigonometric modeling.'),
        ],
        'Chemistry': [
            _unit('Atomic Structure & Bonding', ['Electron Configuration', 'Periodic Trends', 'Ionic Bonding', 'Covalent Bonding'], ['OAS.CHEM.PS1.1', 'OAS.CHEM.PS1.2'], 'Describe matter using atomic models and bonding patterns.'),
            _unit('Chemical Reactions', ['Balancing Equations', 'Stoichiometry', 'Reaction Rates', 'Acids and Bases'], ['OAS.CHEM.PS1.3', 'OAS.CHEM.PS1.4'], 'Predict and quantify chemical change.'),
            _unit('Energy & Solutions', ['Thermochemistry', 'Gas Laws', 'Solutions', 'Lab Safety and Design'], ['OAS.CHEM.PS3.1', 'OAS.CHEM.SE.1'], 'Investigate energy changes and solution chemistry through labs.'),
        ],
        'US History': [
            _unit('Industrialization to Progressivism', ['Gilded Age', 'Labor and Immigration', 'Progressive Era', 'Oklahoma in the Nation'], ['OAS.USH.1', 'OAS.USH.2'], 'Trace growth and reform in the United States.'),
            _unit('Wars & Depression', ['World War I', 'Great Depression', 'New Deal', 'World War II'], ['OAS.USH.3', 'OAS.USH.4'], 'Analyze crisis, recovery, and global conflict.'),
            _unit('Postwar America to Today', ['Cold War', 'Civil Rights Movement', 'Modern Economy', 'Current Civic Issues'], ['OAS.USH.5', 'OAS.USH.6'], 'Study major postwar developments and contemporary issues.'),
        ],
    },
    '12': {
        'English IV': [
            _unit('British & Global Perspectives', ['Early British Texts', 'Satire and Social Critique', 'Modern Global Voices', 'Comparative Analysis'], ['OAS.ELA.12.R.1', 'OAS.ELA.12.R.2'], 'Read across British and global traditions with mature analysis.'),
            _unit('Composition for College & Career', ['Personal Narrative', 'Research Proposal', 'Argument Portfolio', 'Technical Communication'], ['OAS.ELA.12.W.1', 'OAS.ELA.12.W.2'], 'Write for college, career, and public audiences.'),
            _unit('Speaking, Listening & Editing', ['Editing for Style', 'Socratic Seminar', 'Presentation Design', 'Capstone Reflection'], ['OAS.ELA.12.G.1', 'OAS.ELA.12.SL.1'], 'Polish language use and capstone communication skills.'),
        ],
        'Pre-Calculus & Statistics': [
            _unit('Advanced Functions', ['Polynomial and Rational Functions', 'Exponential and Logarithmic Review', 'Inverse Functions', 'Function Composition'], ['OAS.PC.F.1', 'OAS.PC.F.2'], 'Prepare for college math with advanced function analysis.'),
            _unit('Trigonometry', ['Unit Circle', 'Trig Graphs', 'Trig Identities', 'Solving Triangles'], ['OAS.PC.T.1', 'OAS.PC.T.2'], 'Use trigonometric models for periodic phenomena.'),
            _unit('Statistics & Probability', ['Sampling and Bias', 'Normal Models', 'Inference', 'Data-Based Decisions'], ['OAS.PC.D.1', 'OAS.PC.D.2'], 'Analyze data and justify decisions using statistics.'),
        ],
        'Environmental Science': [
            _unit('Earth Systems & Resources', ['Biogeochemical Cycles', 'Water Resources', 'Soils and Land Use', 'Energy Resources'], ['OAS.ENV.ESS2.1', 'OAS.ENV.ESS3.1'], 'Study environmental systems and resource management.'),
            _unit('Ecology & Human Impact', ['Population Dynamics', 'Biodiversity', 'Pollution', 'Climate Change'], ['OAS.ENV.LS2.1', 'OAS.ENV.ESS3.2'], 'Analyze ecological patterns and human impact.'),
            _unit('Solutions & Stewardship', ['Sustainability Plans', 'Environmental Policy', 'Data Collection', 'Community Action Project'], ['OAS.ENV.SE.1', 'OAS.ENV.ETS1.1'], 'Design evidence-based responses to environmental challenges.'),
        ],
        'Government & Economics': [
            _unit('Foundations of Government', ['Constitutional Principles', 'Federalism', 'Civil Liberties', 'Supreme Court Cases'], ['OAS.GOV.1', 'OAS.GOV.2'], 'Understand the structure and principles of US government.'),
            _unit('Participation & Public Policy', ['Political Parties', 'Elections', 'Public Opinion', 'Policy Making'], ['OAS.GOV.3', 'OAS.GOV.4'], 'Examine civic participation and public policy.'),
            _unit('Economics for Citizens', ['Market Structures', 'Fiscal Policy', 'Personal Economic Choices', 'Global Trade'], ['OAS.ECON.1', 'OAS.ECON.2'], 'Apply economics concepts to civic and personal decisions.'),
        ],
    },
}

ELECTIVE_OUTLINES: dict[str, list[dict[str, Any]]] = {
    'Art': [
        _unit('Elements of Art', ['Line and Shape', 'Color Stories', 'Texture Hunt', 'Pattern in Nature'], ['OAS.VA.1', 'OAS.VA.2'], 'Build visual art vocabulary and observation.'),
        _unit('Creating with Media', ['Drawing Basics', 'Paint Mixing', 'Collage Design', 'Clay Form'], ['OAS.VA.3', 'OAS.VA.4'], 'Experiment with a variety of art materials and techniques.'),
        _unit('Responding to Art', ['Gallery Walk', 'Artist Study', 'Oklahoma Art Traditions', 'Reflect and Revise'], ['OAS.VA.5', 'OAS.VA.6'], 'Discuss and reflect on artwork with an Oklahoma perspective.'),
    ],
    'Music': [
        _unit('Rhythm & Beat', ['Steady Beat', 'Quarter and Eighth Notes', 'Rhythm Patterns', 'Movement and Music'], ['OAS.MU.1', 'OAS.MU.2'], 'Use rhythm and movement to build musicianship.'),
        _unit('Melody & Expression', ['High and Low Pitch', 'Solfege Practice', 'Dynamics', 'Folk Songs of Oklahoma'], ['OAS.MU.3', 'OAS.MU.4'], 'Sing, perform, and respond to melodic patterns.'),
        _unit('Performance & Listening', ['Instrument Families', 'Concert Etiquette', 'Create a Pattern', 'Music Reflection'], ['OAS.MU.5', 'OAS.MU.6'], 'Connect listening, performing, and creating in music.'),
    ],
    'Physical Education': [
        _unit('Movement Fundamentals', ['Warm-Up Routines', 'Locomotor Skills', 'Balance and Coordination', 'Fitness Safety'], ['OAS.PE.1', 'OAS.PE.2'], 'Develop movement skills and safe exercise habits.'),
        _unit('Teamwork & Games', ['Cooperative Games', 'Throwing and Catching', 'Soccer Footwork', 'Basketball Basics'], ['OAS.PE.3', 'OAS.PE.4'], 'Practice teamwork, sportsmanship, and game skills.'),
        _unit('Healthy Habits', ['Heart Rate Checks', 'Goal Setting', 'Flexibility', 'Lifetime Fitness'], ['OAS.PE.5', 'OAS.PE.6'], 'Track fitness goals and lifelong wellness habits.'),
    ],
    'Health': [
        _unit('Personal Wellness', ['Nutrition Basics', 'Sleep and Recovery', 'Personal Hygiene', 'Mental Health Check-Ins'], ['OAS.HL.1', 'OAS.HL.2'], 'Understand habits that support physical and emotional wellness.'),
        _unit('Safety & Relationships', ['Digital Safety', 'Healthy Relationships', 'Decision Making', 'Conflict Resolution'], ['OAS.HL.3', 'OAS.HL.4'], 'Develop safe, respectful relationship and communication skills.'),
        _unit('Prevention & Advocacy', ['Substance Abuse Prevention', 'Stress Management', 'Community Resources', 'Health Advocacy'], ['OAS.HL.5', 'OAS.HL.6'], 'Use advocacy and prevention strategies in everyday life.'),
    ],
    'Fine Arts': [
        _unit('Creative Foundations', ['Artistic Processes', 'Observation Sketches', 'Music and Mood', 'Design Principles'], ['OAS.FA.1', 'OAS.FA.2'], 'Survey creative processes across fine arts disciplines.'),
        _unit('Performance & Production', ['Stage Presence', 'Studio Practice', 'Critique Protocols', 'Creative Collaboration'], ['OAS.FA.3', 'OAS.FA.4'], 'Use production and critique routines in the arts.'),
        _unit('Arts in Oklahoma', ['Indigenous Arts', 'Oklahoma Musicians', 'Museum Collections', 'Portfolio Reflection'], ['OAS.FA.5', 'OAS.FA.6'], 'Connect the arts to Oklahoma culture and reflection.'),
    ],
    'Introduction to Computer Science': [
        _unit('Computing Foundations', ['Binary and Data', 'Algorithms', 'Flowcharts', 'Debugging Basics'], ['OAS.CS.1', 'OAS.CS.2'], 'Introduce foundational computer science habits and vocabulary.'),
        _unit('Programming Concepts', ['Variables', 'Conditionals', 'Loops', 'Simple Projects'], ['OAS.CS.3', 'OAS.CS.4'], 'Build simple programs and explain their logic.'),
        _unit('Digital Citizenship', ['Networks', 'Cyber Safety', 'Ethics in Technology', 'Capstone App Pitch'], ['OAS.CS.5', 'OAS.CS.6'], 'Connect computing to ethics, safety, and communication.'),
    ],
    'Spanish I': [
        _unit('Novice Communication', ['Greetings', 'Numbers and Dates', 'Classroom Expressions', 'Introduce Yourself'], ['OAS.WL.1', 'OAS.WL.2'], 'Build novice-level listening and speaking skills in Spanish.'),
        _unit('Daily Life & Culture', ['Family Vocabulary', 'Foods and Preferences', 'School Day', 'Cultural Comparisons'], ['OAS.WL.3', 'OAS.WL.4'], 'Use Spanish in everyday topics while exploring culture.'),
        _unit('Reading & Writing Basics', ['Short Readings', 'Descriptive Sentences', 'Present Tense Verbs', 'Mini Conversation'], ['OAS.WL.5', 'OAS.WL.6'], 'Develop introductory reading and writing skills in Spanish.'),
    ],
    'Personal Finance': [
        _unit('Budgeting & Saving', ['Income and Expenses', 'Budget Plans', 'Emergency Funds', 'Goal Tracking'], ['OAS.PF.1', 'OAS.PF.2'], 'Plan realistic budgets and savings goals.'),
        _unit('Credit & Consumer Skills', ['Credit Scores', 'Loans and Interest', 'Smart Shopping', 'Fraud Prevention'], ['OAS.PF.3', 'OAS.PF.4'], 'Make informed consumer and credit decisions.'),
        _unit('Career & Investing', ['Career Earnings', 'Taxes', 'Intro to Investing', 'Insurance Basics'], ['OAS.PF.5', 'OAS.PF.6'], 'Connect personal finance choices to long-term goals.'),
    ],
    'Psychology': [
        _unit('Foundations of Psychology', ['Schools of Thought', 'Research Methods', 'Ethics', 'Psychology Careers'], ['OAS.PSY.1', 'OAS.PSY.2'], 'Survey the major ideas and methods of psychology.'),
        _unit('Human Development & Cognition', ['Brain Basics', 'Learning and Memory', 'Lifespan Development', 'Personality'], ['OAS.PSY.3', 'OAS.PSY.4'], 'Study cognition and human development through evidence.'),
        _unit('Behavior & Society', ['Motivation', 'Stress and Coping', 'Social Influence', 'Wellness Reflection'], ['OAS.PSY.5', 'OAS.PSY.6'], 'Connect psychology concepts to behavior and wellness.'),
    ],
}

ASSIGNMENT_BLUEPRINTS: tuple[dict[str, Any], ...] = (
    {'suffix': 'Reading Response', 'category': AssignmentCategory.homework, 'period': 'Q1', 'status': AssignmentStatus.graded, 'score': 92, 'graded_by': GradedBy.ai},
    {'suffix': 'Skills Check', 'category': AssignmentCategory.quiz, 'period': 'Q1', 'status': AssignmentStatus.graded, 'score': 84, 'graded_by': GradedBy.human},
    {'suffix': 'Lab Notes', 'category': AssignmentCategory.homework, 'period': 'Q1', 'status': AssignmentStatus.complete, 'score': None, 'graded_by': None},
    {'suffix': 'Unit Quiz', 'category': AssignmentCategory.quiz, 'period': 'Q1', 'status': AssignmentStatus.graded, 'score': 76, 'graded_by': GradedBy.ai_human},
    {'suffix': 'Project Plan', 'category': AssignmentCategory.project, 'period': 'Q1', 'status': AssignmentStatus.pending, 'score': None, 'graded_by': None},
    {'suffix': 'Essay Draft', 'category': AssignmentCategory.homework, 'period': 'Q2', 'status': AssignmentStatus.complete, 'score': None, 'graded_by': None},
    {'suffix': 'Quarter Test', 'category': AssignmentCategory.test, 'period': 'Q2', 'status': AssignmentStatus.graded, 'score': 88, 'graded_by': GradedBy.human},
    {'suffix': 'Creative Project', 'category': AssignmentCategory.project, 'period': 'Q2', 'status': AssignmentStatus.graded, 'score': 95, 'graded_by': GradedBy.ai},
    {'suffix': 'Practice Set', 'category': AssignmentCategory.homework, 'period': 'Q2', 'status': AssignmentStatus.pending, 'score': None, 'graded_by': None},
    {'suffix': 'Reflection Check', 'category': AssignmentCategory.quiz, 'period': 'Q2', 'status': AssignmentStatus.graded, 'score': 69, 'graded_by': GradedBy.human},
)

CALENDAR_EVENTS: tuple[dict[str, Any], ...] = (
    {'name': 'Labor Day', 'date': date(2025, 9, 1), 'event_type': CalendarEventType.holiday, 'is_instructional_day': False, 'notes': 'No classes.'},
    {'name': 'Fall Break', 'date': date(2025, 10, 16), 'event_type': CalendarEventType.closure, 'is_instructional_day': False, 'notes': 'Fall break runs Oct 16-17.'},
    {'name': 'Thanksgiving Break', 'date': date(2025, 11, 24), 'event_type': CalendarEventType.closure, 'is_instructional_day': False, 'notes': 'Thanksgiving break runs Nov 24-28.'},
    {'name': 'Winter Break', 'date': date(2025, 12, 22), 'event_type': CalendarEventType.closure, 'is_instructional_day': False, 'notes': 'Winter break runs Dec 22-Jan 2.'},
    {'name': 'MLK Day', 'date': date(2026, 1, 19), 'event_type': CalendarEventType.holiday, 'is_instructional_day': False, 'notes': 'Martin Luther King Jr. Day.'},
    {'name': 'Presidents Day', 'date': date(2026, 2, 16), 'event_type': CalendarEventType.holiday, 'is_instructional_day': False, 'notes': 'Presidents Day holiday.'},
    {'name': 'Spring Break', 'date': date(2026, 3, 16), 'event_type': CalendarEventType.closure, 'is_instructional_day': False, 'notes': 'Spring break runs Mar 16-20.'},
    {'name': 'Last Day', 'date': date(2026, 5, 22), 'event_type': CalendarEventType.custom, 'is_instructional_day': True, 'notes': 'Last instructional day of the school year.'},
)
ASSIGNMENT_DUE_DATES: tuple[date, ...] = (
    date(2025, 8, 22),
    date(2025, 8, 29),
    date(2025, 9, 12),
    date(2025, 9, 26),
    date(2025, 10, 10),
    date(2025, 10, 24),
    date(2025, 11, 7),
    date(2025, 11, 14),
    date(2025, 12, 5),
    date(2025, 12, 12),
)


def _slugify(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')


def _as_datetime(value: date, hour: int = 15) -> datetime:
    return datetime(value.year, value.month, value.day, hour, 0, tzinfo=UTC)


def _curriculum_outline(spec: StudentSpec, subject_title: str) -> list[dict[str, Any]]:
    grade_outline = CURRICULUM_MAP.get(spec.grade, {})
    outline = grade_outline.get(subject_title) or ELECTIVE_OUTLINES.get(subject_title)
    if outline:
        return outline
    return [
        _unit(
            f'{subject_title} Foundations',
            ['Key Vocabulary', 'Core Concepts', 'Guided Practice', 'Reflection'],
            [f'OAS.{spec.grade}.{_slugify(subject_title).upper()}.1'],
            f'Foundational {subject_title} concepts for grade {spec.grade}.',
        ),
        _unit(
            f'{subject_title} Application',
            ['Close Reading', 'Hands-On Task', 'Data and Discussion', 'Performance Check'],
            [f'OAS.{spec.grade}.{_slugify(subject_title).upper()}.2'],
            f'Practice applying {subject_title} ideas in Oklahoma-aligned tasks.',
        ),
        _unit(
            f'{subject_title} Synthesis',
            ['Project Launch', 'Research and Drafting', 'Peer Review', 'Presentation'],
            [f'OAS.{spec.grade}.{_slugify(subject_title).upper()}.3'],
            f'Synthesize {subject_title} learning in a culminating performance task.',
        ),
    ]


def _instructional_days() -> list[date]:
    blocked_ranges = (
        (date(2025, 9, 1), date(2025, 9, 1)),
        (date(2025, 10, 16), date(2025, 10, 17)),
        (date(2025, 11, 24), date(2025, 11, 28)),
        (date(2025, 12, 22), date(2026, 1, 2)),
        (date(2026, 1, 19), date(2026, 1, 19)),
        (date(2026, 2, 16), date(2026, 2, 16)),
        (date(2026, 3, 16), date(2026, 3, 20)),
    )
    results: list[date] = []
    current = SCHOOL_YEAR_START
    while current <= SCHOOL_YEAR_END and len(results) < 60:
        if current.weekday() < 5 and not any(start <= current <= end for start, end in blocked_ranges):
            results.append(current)
        current += timedelta(days=1)
    return results


def _period_for_date(grading_periods: dict[str, GradingPeriod], due_date: date) -> GradingPeriod:
    if due_date <= grading_periods['Q1'].end_date:
        return grading_periods['Q1']
    return grading_periods['Q2']


def _subject_display_name(spec: StudentSpec, subject_title: str) -> str:
    return f'{subject_title} ({spec.name})'


async def seed_demo_data(session: AsyncSession) -> bool:
    demo_family = (
        await session.execute(
            select(Family.id).where(
                Family.settings['demo_mode'].as_boolean() == True  # noqa: E712
            ).limit(1)
        )
    ).scalar_one_or_none()
    if demo_family is not None:
        return False

    # Remove bootstrap family/user created by migration so demo data owns the DB
    await session.execute(delete(FamilyMembership))
    await session.execute(delete(FamilySettings))
    await session.execute(delete(Family))
    await session.execute(delete(UserPreference))
    await session.execute(delete(User))
    await session.flush()

    family = Family(
        name='Demo Family',
        settings={'timezone': 'America/Chicago', 'state_code': 'OK', 'grading_scale': 'letter', 'demo_mode': True},
    )
    user = User(
        email=normalize_email(DEMO_EMAIL),
        display_name='Demo Parent',
        password_hash=hash_password(DEMO_PASSWORD),
        is_active=True,
    )
    membership = FamilyMembership(user=user, family=family, role=FamilyRole.parent, is_owner=True, accepted_at=datetime.now(UTC))
    family_settings = FamilySettings(family=family, timezone='America/Chicago', state_code='OK', grading_scale='letter')
    user_preferences = UserPreference(user=user, **DEFAULT_USER_PREFERENCES.model_dump())
    session.add_all([family, user, membership, family_settings, user_preferences])
    await session.flush()

    grade_scale = await _create_default_grade_scale(session, family.id)

    school_year = SchoolYear(
        family_id=family.id,
        name=SCHOOL_YEAR_NAME,
        start_date=SCHOOL_YEAR_START,
        end_date=SCHOOL_YEAR_END,
        is_active=True,
    )
    session.add(school_year)
    await session.flush()

    fall_term = Term(
        family_id=family.id,
        school_year=school_year,
        name='Fall Semester',
        start_date=date(2025, 8, 11),
        end_date=date(2025, 12, 19),
        term_type=TermType.semester,
    )
    spring_term = Term(
        family_id=family.id,
        school_year=school_year,
        name='Spring Semester',
        start_date=date(2026, 1, 5),
        end_date=date(2026, 5, 22),
        term_type=TermType.semester,
    )
    session.add_all([fall_term, spring_term])
    await session.flush()

    grading_periods = {
        'Q1': GradingPeriod(family_id=family.id, term=fall_term, name='Q1', start_date=date(2025, 8, 11), end_date=date(2025, 10, 10)),
        'Q2': GradingPeriod(family_id=family.id, term=fall_term, name='Q2', start_date=date(2025, 10, 13), end_date=date(2025, 12, 19)),
        'Q3': GradingPeriod(family_id=family.id, term=spring_term, name='Q3', start_date=date(2026, 1, 5), end_date=date(2026, 3, 13)),
        'Q4': GradingPeriod(family_id=family.id, term=spring_term, name='Q4', start_date=date(2026, 3, 16), end_date=date(2026, 5, 22)),
    }
    session.add_all(list(grading_periods.values()))

    for event in CALENDAR_EVENTS:
        session.add(CalendarEvent(family_id=family.id, school_year=school_year, **event))

    attendance_days = _instructional_days()

    for student_index, spec in enumerate(STUDENT_SPECS):
        student = Student(family_id=family.id, name=spec.name)
        session.add(student)
        await session.flush()

        subject_objects: list[Subject] = []
        for subject_title in spec.subject_titles:
            subject = Subject(
                family_id=family.id,
                name=_subject_display_name(spec, subject_title),
                color=_subject_color(subject_title),
                grading_mode=SubjectGradingMode.points,
                grade_scale=grade_scale,
            )
            session.add(subject)
            await session.flush()
            subject_objects.append(subject)

            for category in build_default_grade_categories(['homework', 'quiz', 'test', 'project']):
                session.add(
                    GradeCategory(
                        family_id=family.id,
                        subject=subject,
                        name=str(category['name']),
                        weight=float(category['weight']),
                        drop_lowest=int(category.get('drop_lowest') or 0),
                    )
                )

            package = CurriculumPackage(
                family_id=family.id,
                school_year=school_year,
                name=f'{subject.name} Pathway',
                description=f'Oklahoma standards-aligned {subject_title} sequence for {spec.name} in grade {spec.grade}.',
                subject=subject,
                created_by_user=user,
            )
            session.add(package)
            await session.flush()

            for unit_index, unit_payload in enumerate(_curriculum_outline(spec, subject_title), start=1):
                unit = CurriculumUnit(
                    package=package,
                    name=str(unit_payload['name']),
                    description=str(unit_payload['description']),
                    sequence_order=unit_index,
                    standards_tags=list(unit_payload['standards_tags']),
                )
                session.add(unit)
                await session.flush()
                for lesson_index, lesson_payload in enumerate(unit_payload['lessons'], start=1):
                    session.add(
                        CurriculumLesson(
                            unit=unit,
                            name=str(lesson_payload['name']),
                            description=f"{lesson_payload['name']} for {subject_title.lower()} in grade {spec.grade}.",
                            sequence_order=lesson_index,
                            estimated_duration_minutes=40 if spec.grade in {'K', '1', '2', '3', '4', '5'} else 50,
                            standards_tags=list(unit_payload['standards_tags']),
                        )
                    )

        _seed_assignments_for_student(
            session=session,
            family_id=family.id,
            student=student,
            subjects=subject_objects,
            grading_periods=grading_periods,
            student_index=student_index,
            grade_scale=grade_scale,
        )
        _seed_attendance_for_student(
            session=session,
            family_id=family.id,
            user=user,
            student=student,
            school_days=attendance_days,
            student_index=student_index,
        )

    await session.commit()
    logger.info('Seeded Oklahoma K-12 demo data for Demo Family with %s students', len(STUDENT_SPECS))
    return True


async def _create_default_grade_scale(session: AsyncSession, family_id: int) -> GradeScale:
    grade_scale = GradeScale(
        family_id=family_id,
        name=DEFAULT_GRADE_SCALE_NAME,
        ranges=list(DEFAULT_GRADE_SCALE_RANGES),
        is_default=True,
    )
    session.add(grade_scale)
    await session.flush()
    return grade_scale


def _subject_color(subject_title: str) -> str:
    palette = {
        'English Language Arts': '#7c3aed',
        'English I': '#7c3aed',
        'English II': '#7c3aed',
        'English III': '#7c3aed',
        'English IV': '#7c3aed',
        'Mathematics': '#2563eb',
        'Algebra I': '#2563eb',
        'Geometry': '#2563eb',
        'Algebra II': '#2563eb',
        'Pre-Calculus & Statistics': '#2563eb',
        'Science': '#059669',
        'Physical Science': '#059669',
        'Biology': '#059669',
        'Chemistry': '#059669',
        'Environmental Science': '#059669',
        'Social Studies': '#ea580c',
        'Oklahoma History': '#ea580c',
        'World History': '#ea580c',
        'US History': '#ea580c',
        'Government & Economics': '#ea580c',
        'Art': '#db2777',
        'Music': '#f59e0b',
        'Fine Arts': '#db2777',
        'Physical Education': '#10b981',
        'Health': '#14b8a6',
    }
    return palette.get(subject_title, '#4f46e5')


def _seed_assignments_for_student(
    *,
    session: AsyncSession,
    family_id: int,
    student: Student,
    subjects: list[Subject],
    grading_periods: dict[str, GradingPeriod],
    student_index: int,
    grade_scale: Any,
) -> None:
    for assignment_index, blueprint in enumerate(ASSIGNMENT_BLUEPRINTS):
        subject = subjects[assignment_index % len(subjects)]
        due_day = ASSIGNMENT_DUE_DATES[assignment_index] + timedelta(days=student_index % 3)
        grading_period = _period_for_date(grading_periods, due_day)
        due_at = _as_datetime(due_day, hour=15)

        assignment = Assignment(
            family_id=family_id,
            title=f'{subject.name} {blueprint["suffix"]}',
            subject=subject,
            description=f'{blueprint["suffix"]} aligned to Oklahoma standards for {student.name}.',
            due_date=due_at,
            status=blueprint['status'],
            category=blueprint['category'],
            grading_period=grading_period,
            weight=1.0,
            max_score=100.0,
            status_history=[{'status': blueprint['status'].value, 'at': due_at.isoformat()}],
        )
        target_status = AssignmentTargetStatus.assigned
        completed_at = None
        if blueprint['status'] == AssignmentStatus.complete:
            target_status = AssignmentTargetStatus.submitted
            completed_at = due_at - timedelta(hours=2)
        elif blueprint['status'] == AssignmentStatus.graded:
            target_status = AssignmentTargetStatus.graded
            completed_at = due_at - timedelta(hours=3)

        target = AssignmentTarget(
            assignment=assignment,
            student=student,
            due_date=due_at,
            status=target_status,
            completed_at=completed_at,
        )
        session.add_all([assignment, target])

        if blueprint['status'] in {AssignmentStatus.complete, AssignmentStatus.graded}:
            submission = Submission(
                family_id=family_id,
                assignment=assignment,
                student=student,
                file_path=f'demo/{_slugify(student.name)}/{_slugify(assignment.title)}.txt',
                original_filename=f'{_slugify(assignment.title)}.txt',
                file_name=f'{_slugify(assignment.title)}.txt',
                file_type='text/plain',
                file_size_bytes=2048 + (assignment_index * 128),
                submission_version=1,
                is_current=True,
                ocr_text=f'Demo submission text for {assignment.title}.',
                uploaded_at=completed_at or (due_at - timedelta(hours=1)),
            )
            session.add(submission)

            if blueprint['status'] == AssignmentStatus.graded and blueprint['score'] is not None and blueprint['graded_by'] is not None:
                percent = float(blueprint['score'])
                letter_grade, _ = map_percent_to_grade(grade_scale, percent)
                session.add(
                    Grade(
                        family_id=family_id,
                        submission=submission,
                        student=student,
                        score=percent,
                        max_score=100.0,
                        letter_grade=letter_grade,
                        notes=f'{blueprint["suffix"]} scored during demo seeding.',
                        graded_by=blueprint['graded_by'],
                        ai_confidence=0.94 if blueprint['graded_by'] != GradedBy.human else None,
                    )
                )


def _seed_attendance_for_student(
    *,
    session: AsyncSession,
    family_id: int,
    user: User,
    student: Student,
    school_days: list[date],
    student_index: int,
) -> None:
    absent_indexes = {5 + (student_index % 4), 18 + (student_index % 5)}
    excused_indexes = {32 + (student_index % 4)}
    if student_index % 2 == 0:
        excused_indexes.add(46 + (student_index % 5))

    for day_index, school_day in enumerate(school_days):
        if day_index in excused_indexes:
            record = AttendanceRecord(
                family_id=family_id,
                student=student,
                date=school_day,
                status=AttendanceStatus.excused,
                instructional_hours=Decimal('0.00'),
                notes='Excused family appointment.',
            )
            session.add(record)
            session.add(
                AttendanceExcuse(
                    family_id=family_id,
                    attendance_record=record,
                    reason='Family appointment',
                    approved_by=user,
                    approved_at=_as_datetime(school_day, hour=18),
                )
            )
            continue

        if day_index in absent_indexes:
            session.add(
                AttendanceRecord(
                    family_id=family_id,
                    student=student,
                    date=school_day,
                    status=AttendanceStatus.absent,
                    instructional_hours=Decimal('0.00'),
                    notes='Unplanned absence.',
                )
            )
            continue

        is_tardy = day_index == (9 + student_index)
        session.add(
            AttendanceRecord(
                family_id=family_id,
                student=student,
                date=school_day,
                status=AttendanceStatus.tardy if is_tardy else AttendanceStatus.present,
                check_in_time=time(9, 5) if is_tardy else time(8, 30),
                check_out_time=time(15, 0),
                instructional_hours=Decimal('5.50') if is_tardy else Decimal('6.00'),
                notes='Late arrival due to morning appointment.' if is_tardy else None,
            )
        )
