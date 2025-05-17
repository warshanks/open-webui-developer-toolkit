from openwebui_devtoolkit.pipes.openai_responses_api_pipeline import (
    build_responses_payload,
    prepare_tools,
    pretty_log_block,
)


def test_prepare_tools_variants():
    reg = {
        'tools': {
            'one': {'spec': {'name': 'foo', 'description': 'd', 'parameters': {'type': 'object'}}},
            'two': {'spec': {'function': {'name': 'bar'}}},
        }
    }
    tools = prepare_tools(reg)
    assert tools[0]['name'] == 'foo'
    assert tools[1]['name'] == 'bar'
    assert tools[0]['type'] == tools[1]['type'] == 'function'


def test_build_responses_payload(stub_open_webui):
    stub_open_webui['history'] = {
        'currentId': 'm2',
        'messages': {
            'm1': {'role': 'user', 'content': [{'text': 'hi'}], 'parentId': None},
            'm2': {'role': 'assistant', 'content': [{'text': 'hello'}], 'parentId': 'm1'},
        },
    }

    payload = build_responses_payload('chat1')
    assert payload == [
        {'role': 'user', 'content': [{'type': 'input_text', 'text': 'hi'}]},
        {'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'hello'}]},
    ]


def test_pretty_log_block():
    out = pretty_log_block({'a': 1}, label='lbl')
    assert 'lbl =' in out
    assert '{\n  "a": 1\n}' in out
