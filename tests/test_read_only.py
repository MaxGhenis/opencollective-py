"""Tests for read-only mode (OPENCOLLECTIVE_READ_ONLY).

Invariant: while read-only mode is on, no GraphQL mutation and no file upload
leaves the client, whichever public method is called; queries still go out.
With the mode off, the same write methods do send their mutation or upload,
which shows the fake transport below reaches the write path at all.
"""

import json
import re

import pytest
import responses
from click.testing import CliRunner
from hypothesis import given, settings
from hypothesis import strategies as st

from opencollective import OpenCollectiveClient, ReadOnlyError, read_only_enabled
from opencollective import client as client_module
from opencollective.cli import cli

from .conftest import API_URL

ENV = "OPENCOLLECTIVE_READ_ONLY"

# One answer for every query: holds each field the write methods read before
# they write (an expense with two items, the viewer, a payout method).
READ_DATA = {
    "expense": {
        "id": "exp-1",
        "legacyId": 12345,
        "description": "Existing expense",
        "items": [
            {"id": "item-1", "description": "first", "amount": 100},
            {"id": "item-2", "description": "second", "amount": 200},
        ],
    },
    "me": {"id": "user-1", "slug": "payee"},
    "account": {"id": "acct-1", "slug": "payee", "payoutMethods": [{"id": "pm-1"}]},
    "collective": {"id": "col-1", "slug": "collective", "currency": "USD"},
    "expenses": {"totalCount": 0, "nodes": []},
}
WRITE_DATA = {
    key: {"id": "exp-9", "legacyId": 9, "status": "PENDING"}
    for key in (
        "processExpense",
        "createExpense",
        "editExpense",
        "deleteExpense",
    )
}


def _is_mutation_doc(query: str) -> bool:
    """Oracle written apart from the client's regex: split on non-word runs."""
    return any(tok.lower() == "mutation" for tok in re.split(r"\W+", query))


class FakeTransport:
    """Stands in for the network: records every request, answers queries."""

    def __init__(self):
        self.graphql = []  # query documents sent through the session
        self.uploads = 0

    def session_post(self, url, json=None, **kwargs):
        query = (json or {}).get("query", "")
        self.graphql.append(query)
        data = WRITE_DATA if _is_mutation_doc(query) else READ_DATA
        return _Response({"data": data})

    def upload_post(self, url, files=None, headers=None, **kwargs):
        self.uploads += 1
        return _Response(
            {"data": {"uploadFile": [{"file": {"url": "https://files/x.pdf"}}]}}
        )

    @property
    def mutations_sent(self):
        return [q for q in self.graphql if _is_mutation_doc(q)]


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture
def receipt(tmp_path):
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"%PDF-1.4 test receipt")
    return str(path)


@pytest.fixture
def transport(client, monkeypatch):
    fake = FakeTransport()
    monkeypatch.setattr(client._session, "post", fake.session_post)
    monkeypatch.setattr(client_module.requests, "post", fake.upload_post)
    return fake


def _write_calls(receipt):
    """Every public write path, as (label, call(client))."""
    return [
        ("approve legacy id", lambda c: c.approve_expense(12345)),
        ("approve public id", lambda c: c.approve_expense("exp-1")),
        ("reject", lambda c: c.reject_expense(12345, "duplicate")),
        ("delete legacy id", lambda c: c.delete_expense(12345)),
        ("delete public id", lambda c: c.delete_expense("exp-1")),
        ("edit", lambda c: c.edit_expense("exp-1", description="new")),
        ("edit legacy id", lambda c: c.edit_expense(12345, tags=["a"])),
        (
            "add item",
            lambda c: c.add_expense_item(12345, "third", 300, receipt),
        ),
        ("remove item", lambda c: c.remove_expense_item("exp-1", item_index=1)),
        (
            "create",
            lambda c: c.create_expense("collective", "payee", "desc", 100),
        ),
        (
            "submit reimbursement",
            lambda c: c.submit_reimbursement("collective", "desc", 100, receipt),
        ),
        (
            "submit multi-item",
            lambda c: c.submit_multi_item_reimbursement(
                "collective",
                "desc",
                [{"amount_cents": 100, "description": "a", "receipt_file": receipt}],
            ),
        ),
        ("submit invoice", lambda c: c.submit_invoice("collective", "desc", 100)),
        (
            "submit invoice with file",
            lambda c: c.submit_invoice("collective", "desc", 100, invoice_file=receipt),
        ),
        ("upload", lambda c: c.upload_file(receipt)),
        (
            "raw mutation",
            lambda c: c._request("mutation { deleteExpense(expense: {}) { id } }"),
        ),
    ]


WRITE_LABELS = [label for label, _ in _write_calls("unused")]


def _call(label, receipt):
    return dict(_write_calls(receipt))[label]


class TestReadOnlyEnabled:
    @pytest.mark.parametrize(
        "value", ["1", "true", "TRUE", "yes", "on", " 1 ", "enabled", "2"]
    )
    def test_on(self, value):
        assert read_only_enabled({ENV: value})

    @pytest.mark.parametrize(
        "value", ["", "0", "false", "False", "NO", "off", " 0 ", "\tfalse\n"]
    )
    def test_off(self, value):
        assert not read_only_enabled({ENV: value})

    def test_unset_is_off(self):
        assert not read_only_enabled({})

    def test_reads_os_environ_by_default(self, monkeypatch):
        assert not read_only_enabled()
        monkeypatch.setenv(ENV, "1")
        assert read_only_enabled()

    @given(st.text())
    def test_only_the_off_words_turn_it_off(self, value):
        off = value.strip().lower() in {"", "0", "false", "no", "off"}
        assert read_only_enabled({ENV: value}) is not off


class TestWritesRefused:
    @pytest.mark.parametrize("label", WRITE_LABELS)
    def test_refused_and_nothing_sent(
        self, label, client, transport, receipt, monkeypatch
    ):
        monkeypatch.setenv(ENV, "1")
        with pytest.raises(ReadOnlyError, match="read-only"):
            _call(label, receipt)(client)
        assert transport.mutations_sent == []
        assert transport.uploads == 0

    @pytest.mark.parametrize("label", WRITE_LABELS)
    def test_same_call_writes_when_off(self, label, client, transport, receipt):
        _call(label, receipt)(client)
        assert transport.mutations_sent or transport.uploads

    def test_refusal_names_the_mutation(self, client, transport, monkeypatch):
        monkeypatch.setenv(ENV, "1")
        with pytest.raises(ReadOnlyError, match="mutation ProcessExpense"):
            client.approve_expense(12345)

    def test_flag_set_after_construction_still_applies(self, transport, monkeypatch):
        late = OpenCollectiveClient(access_token="test_token")
        monkeypatch.setattr(late._session, "post", transport.session_post)
        monkeypatch.setenv(ENV, "1")
        with pytest.raises(ReadOnlyError):
            late.delete_expense(12345)
        assert transport.graphql == []

    def test_refusal_is_a_permission_error(self):
        assert issubclass(ReadOnlyError, PermissionError)


class TestReadsAllowed:
    @pytest.mark.parametrize(
        "call",
        [
            lambda c: c.get_expenses("collective"),
            lambda c: c.get_expense(12345),
            lambda c: c.get_me(),
            lambda c: c.get_collective("collective"),
            lambda c: c.get_payout_methods("payee"),
        ],
    )
    def test_query_goes_out(self, call, client, transport, monkeypatch):
        monkeypatch.setenv(ENV, "1")
        call(client)
        assert len(transport.graphql) == 1
        assert transport.mutations_sent == []


# Fragments for generated GraphQL-ish documents, chosen to hit the edge of the
# word match: the keyword in any case, inside longer words, in comments.
FRAGMENTS = st.sampled_from(
    [
        "mutation",
        "Mutation",
        "MUTATION",
        "mutations",
        "mutationType",
        "premutation",
        "_mutation",
        "query",
        "Q",
        "{",
        "}",
        "(",
        ")",
        "$id: Int!",
        "expense",
        "# comment",
        "\n",
        " ",
        "\t",
        ",",
        "__schema",
    ]
)
DOCUMENTS = st.lists(FRAGMENTS | st.text(max_size=8), max_size=12).map("".join)


class TestRequestProperty:
    @settings(max_examples=300)
    @given(DOCUMENTS)
    def test_refused_iff_mutation_word_when_on(self, query):
        client = OpenCollectiveClient(access_token="test_token")
        fake = FakeTransport()
        client._session.post = fake.session_post
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv(ENV, "1")
            if _is_mutation_doc(query):
                with pytest.raises(ReadOnlyError):
                    client._request(query)
                assert fake.graphql == []
            else:
                client._request(query)
                assert fake.graphql == [query]

    @settings(max_examples=300)
    @given(DOCUMENTS)
    def test_never_refused_when_off(self, query):
        client = OpenCollectiveClient(access_token="test_token")
        fake = FakeTransport()
        client._session.post = fake.session_post
        client._request(query)
        assert fake.graphql == [query]


class TestCli:
    @responses.activate
    @pytest.mark.parametrize(
        "args",
        [
            ["approve", "12345"],
            ["reject", "12345", "-m", "duplicate"],
            ["delete", "12345"],
            ["edit", "exp-1", "--description", "new"],
        ],
    )
    def test_write_commands_refused(self, args, mock_token, monkeypatch):
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)
        monkeypatch.setenv(ENV, "1")
        result = CliRunner().invoke(cli, args)
        assert result.exit_code == 1
        assert "read-only" in result.output
        assert len(responses.calls) == 0

    @responses.activate
    def test_bulk_approve_refused_with_exit_1(self, mock_token, monkeypatch):
        """--all-mine catches per-expense errors; a read-only refusal must
        still stop the run with exit 1 rather than report 'failed N'."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)
        monkeypatch.setenv(ENV, "1")
        responses.add(responses.POST, API_URL, json={"data": {"me": {"slug": "payee"}}})
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 2,
                        "nodes": [
                            {
                                "legacyId": 5,
                                "description": "a",
                                "payee": {"slug": "payee"},
                            },
                            {
                                "legacyId": 6,
                                "description": "b",
                                "payee": {"slug": "payee"},
                            },
                        ],
                    }
                }
            },
        )
        result = CliRunner().invoke(cli, ["approve", "--all-mine", "-c", "collective"])
        assert result.exit_code == 1
        assert "read-only" in result.output
        sent = [json.loads(c.request.body.decode())["query"] for c in responses.calls]
        assert len(sent) == 2 and not any(_is_mutation_doc(q) for q in sent)

    @responses.activate
    def test_expenses_listing_still_works(self, mock_token, monkeypatch):
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)
        monkeypatch.setenv(ENV, "1")
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"account": {"expenses": {"totalCount": 0, "nodes": []}}}},
            status=200,
        )
        result = CliRunner().invoke(cli, ["expenses", "-c", "collective"])
        assert result.exit_code == 0, result.output
        body = json.loads(responses.calls[0].request.body.decode())
        assert not _is_mutation_doc(body["query"])
