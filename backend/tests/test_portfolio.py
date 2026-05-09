from __future__ import annotations

from httpx import AsyncClient

from tests.contracts import PORTFOLIO, portfolio_collection_payload, portfolio_entry_payload
from tests.helpers import response_id


async def test_portfolio_entry_crud_and_filters(
    authorized_client: AsyncClient,
    seeded_assignment: dict,
    seeded_student: dict,
    seeded_subject: dict,
    seeded_submission: dict,
):
    create_response = await authorized_client.post(
        PORTFOLIO['entry_collection'],
        json=portfolio_entry_payload(
            response_id(seeded_student),
            entry_type='journal',
            subject_id=response_id(seeded_subject),
            assignment_id=response_id(seeded_assignment),
            submission_id=response_id(seeded_submission),
            tags=['science', 'reflection'],
        ),
    )
    assert create_response.status_code == 201, create_response.text
    entry = create_response.json()
    assert entry['entry_type'] == 'journal'
    assert entry['assignment']['id'] == response_id(seeded_assignment)
    assert entry['submission']['id'] == response_id(seeded_submission)

    listing = await authorized_client.get(
        PORTFOLIO['entries'].format(student_id=response_id(seeded_student)),
        params={'type': 'journal', 'subject_id': response_id(seeded_subject), 'tags': 'science,reflection'},
    )
    assert listing.status_code == 200, listing.text
    assert [item['id'] for item in listing.json()] == [entry['id']]

    update_response = await authorized_client.put(
        PORTFOLIO['entry_detail'].format(entry_id=entry['id']),
        json=portfolio_entry_payload(
            response_id(seeded_student),
            entry_type='milestone',
            title='Museum milestone',
            description='Completed the physics exhibit scavenger hunt.',
            date='2026-05-09',
            subject_id=response_id(seeded_subject),
            assignment_id=response_id(seeded_assignment),
            submission_id=response_id(seeded_submission),
            tags=['science', 'milestone'],
        ),
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated['entry_type'] == 'milestone'
    assert updated['title'] == 'Museum milestone'

    detail_response = await authorized_client.get(PORTFOLIO['entry_detail'].format(entry_id=entry['id']))
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()['tags'] == ['science', 'milestone']

    delete_response = await authorized_client.delete(PORTFOLIO['entry_detail'].format(entry_id=entry['id']))
    assert delete_response.status_code == 204, delete_response.text

    missing_response = await authorized_client.get(PORTFOLIO['entry_detail'].format(entry_id=entry['id']))
    assert missing_response.status_code == 404, missing_response.text


async def test_portfolio_collection_management_and_public_sharing(
    authorized_client: AsyncClient,
    async_client: AsyncClient,
    seeded_student: dict,
):
    first_entry = (
        await authorized_client.post(
            PORTFOLIO['entry_collection'],
            json=portfolio_entry_payload(response_id(seeded_student), entry_type='work_sample', title='Fractions poster'),
        )
    ).json()
    second_entry = (
        await authorized_client.post(
            PORTFOLIO['entry_collection'],
            json=portfolio_entry_payload(response_id(seeded_student), entry_type='journal', title='Weekly journal'),
        )
    ).json()

    create_collection = await authorized_client.post(
        PORTFOLIO['collections'],
        json=portfolio_collection_payload(response_id(seeded_student), [first_entry['id'], second_entry['id']]),
    )
    assert create_collection.status_code == 201, create_collection.text
    collection = create_collection.json()
    assert [item['id'] for item in collection['entries']] == [first_entry['id'], second_entry['id']]

    update_collection = await authorized_client.put(
        PORTFOLIO['collection_detail'].format(collection_id=collection['id']),
        json=portfolio_collection_payload(
            response_id(seeded_student),
            [second_entry['id']],
            name='Journal picks',
            is_public=False,
        ),
    )
    assert update_collection.status_code == 200, update_collection.text
    updated = update_collection.json()
    assert updated['name'] == 'Journal picks'
    assert [item['id'] for item in updated['entries']] == [second_entry['id']]

    share_response = await authorized_client.get(PORTFOLIO['collection_share'].format(collection_id=collection['id']))
    assert share_response.status_code == 200, share_response.text
    share = share_response.json()
    assert share['share_token']
    assert share['url'].endswith(f"/portfolio/share/{share['share_token']}")

    public_response = await async_client.get(PORTFOLIO['public_collection'].format(share_token=share['share_token']))
    assert public_response.status_code == 200, public_response.text
    public_payload = public_response.json()
    assert public_payload['name'] == 'Journal picks'
    assert [item['id'] for item in public_payload['entries']] == [second_entry['id']]


async def test_portfolio_family_isolation_and_scope(
    authorized_client: AsyncClient,
    secondary_client: AsyncClient,
    create_family_user,
    seeded_student: dict,
):
    primary_entry = (
        await authorized_client.post(
            PORTFOLIO['entry_collection'],
            json=portfolio_entry_payload(response_id(seeded_student), title='Family one entry'),
        )
    ).json()

    secondary = await create_family_user(
        family_name='Other Family',
        email='other-parent@example.com',
        password='strongpass123',
        display_name='Other Parent',
    )
    login_response = await secondary_client.post('/api/auth/login', json={'email': secondary['email'], 'password': secondary['password']})
    assert login_response.status_code == 200, login_response.text

    isolated_detail = await secondary_client.get(PORTFOLIO['entry_detail'].format(entry_id=primary_entry['id']))
    assert isolated_detail.status_code == 404, isolated_detail.text

    isolated_list = await secondary_client.get(PORTFOLIO['entries'].format(student_id=response_id(seeded_student)))
    assert isolated_list.status_code == 404, isolated_list.text

    isolated_delete = await secondary_client.delete(PORTFOLIO['entry_detail'].format(entry_id=primary_entry['id']))
    assert isolated_delete.status_code == 404, isolated_delete.text


async def test_portfolio_attachment_handling(
    authorized_client: AsyncClient,
    seeded_student: dict,
):
    create_response = await authorized_client.post(
        PORTFOLIO['entry_collection'],
        json=portfolio_entry_payload(response_id(seeded_student), entry_type='photo', title='Microscope snapshot'),
    )
    assert create_response.status_code == 201, create_response.text
    entry = create_response.json()

    attach_response = await authorized_client.post(
        PORTFOLIO['entry_attach'].format(entry_id=entry['id']),
        files=[
            (
                'files',
                (
                    'sample.png',
                    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0'
                    b'\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82',
                    'image/png',
                ),
            ),
            ('files', ('notes.pdf', b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF', 'application/pdf')),
        ],
    )
    assert attach_response.status_code == 200, attach_response.text
    attached = attach_response.json()
    assert len(attached['attachments']) == 2
    assert all(item.startswith('portfolio\\') or item.startswith('portfolio/') for item in attached['attachments'])
    assert all(url.startswith('/uploads/portfolio/') for url in attached['attachment_urls'])


async def test_student_viewer_can_manage_only_own_portfolio(
    authorized_client: AsyncClient,
    secondary_client: AsyncClient,
    create_family_user,
):
    primary_student_create = await authorized_client.post('/api/students', json={'name': 'Ada Student'})
    assert primary_student_create.status_code == 201, primary_student_create.text
    primary_student = primary_student_create.json()
    other_student_create = await authorized_client.post('/api/students', json={'name': 'Grace Hopper'})
    assert other_student_create.status_code == 201, other_student_create.text
    other_student = other_student_create.json()

    viewer = await create_family_user(
        family_name='Test Family',
        family_id=1,
        email='viewer@example.com',
        password='strongpass123',
        display_name='Student Viewer',
        role='student_viewer',
        student_id=primary_student['id'],
    )
    login_response = await secondary_client.post('/api/auth/login', json={'email': viewer['email'], 'password': viewer['password']})
    assert login_response.status_code == 200, login_response.text

    own_entry_response = await secondary_client.post(
        PORTFOLIO['entry_collection'],
        json=portfolio_entry_payload(primary_student['id'], title='My journal'),
    )
    assert own_entry_response.status_code == 201, own_entry_response.text

    blocked_entry_response = await secondary_client.post(
        PORTFOLIO['entry_collection'],
        json=portfolio_entry_payload(other_student['id'], title='Not my journal'),
    )
    assert blocked_entry_response.status_code == 403, blocked_entry_response.text
