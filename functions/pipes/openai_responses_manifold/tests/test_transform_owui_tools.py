import json
import textwrap

from functions.pipes.openai_responses_manifold.openai_responses_manifold import ResponsesBody

def test_transform_owui_tools():
    __tools__ = {
        "tool_custom_parameter": {
            "tool_id": "mega",
            "callable": "<UNSERIALIZABLE>",
            "spec": {
                "name": "tool_custom_parameter",
                "description": "Covers core parameter shapes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool_array_of_objects": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "inner_optional_name": {"type": "string"},
                                    "inner_required_id": {"type": "integer"},
                                },
                                "required": ["inner_required_id"]
                            }
                        },
                        "tool_fixed_const": {"type": "string", "const": "always"},
                        "tool_mode": {"type": "string", "enum": ["fast", "slow"]},
                        "tool_nested_object": {
                            "type": "object",
                            "properties": {
                                "nested_optional_boolean": {"type": "boolean"},
                                "nested_required_string": {"type": "string"},
                            },
                            "required": ["nested_required_string"]
                        },
                        "tool_optional_array_numbers": {
                            "type": "array",
                            "items": {"type": "number"}
                        },
                        "tool_optional_string": {"type": "string"},
                        "tool_required_array_strings": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "tool_required_string": {"type": "string"},
                        "tool_union_object": {
                            "anyOf": [
                                {"type": "object", "properties": {"union_integer": {"type": "integer"}}},
                                {"type": "object", "properties": {"union_string": {"type": "string"}}}
                            ]
                        }
                    },
                    "required": [
                        "tool_required_string",
                        "tool_nested_object",
                        "tool_required_array_strings"
                    ]
                },
            },
            "metadata": {"file_handler": False, "citation": False},
        }
    }

    out = ResponsesBody.transform_owui_tools(__tools__, strict=True)

    # One tool only; deterministic stringify
    actual = json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False)

    expected = textwrap.dedent("""
    [
      {
        "description": "Covers core parameter shapes.",
        "name": "tool_custom_parameter",
        "parameters": {
          "additionalProperties": false,
          "properties": {
            "tool_array_of_objects": {
              "items": {
                "additionalProperties": false,
                "properties": {
                  "inner_optional_name": {
                    "type": [
                      "string",
                      "null"
                    ]
                  },
                  "inner_required_id": {
                    "type": "integer"
                  }
                },
                "required": [
                  "inner_optional_name",
                  "inner_required_id"
                ],
                "type": "object"
              },
              "type": [
                "array",
                "null"
              ]
            },
            "tool_fixed_const": {
              "const": "always",
              "type": [
                "string",
                "null"
              ]
            },
            "tool_mode": {
              "enum": [
                "fast",
                "slow"
              ],
              "type": [
                "string",
                "null"
              ]
            },
            "tool_nested_object": {
              "additionalProperties": false,
              "properties": {
                "nested_optional_boolean": {
                  "type": [
                    "boolean",
                    "null"
                  ]
                },
                "nested_required_string": {
                  "type": "string"
                }
              },
              "required": [
                "nested_optional_boolean",
                "nested_required_string"
              ],
              "type": "object"
            },
            "tool_optional_array_numbers": {
              "items": {
                "type": "number"
              },
              "type": [
                "array",
                "null"
              ]
            },
            "tool_optional_string": {
              "type": [
                "string",
                "null"
              ]
            },
            "tool_required_array_strings": {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            "tool_required_string": {
              "type": "string"
            },
            "tool_union_object": {
              "anyOf": [
                {
                  "additionalProperties": false,
                  "properties": {
                    "union_integer": {
                      "type": [
                        "integer",
                        "null"
                      ]
                    }
                  },
                  "required": [
                    "union_integer"
                  ],
                  "type": "object"
                },
                {
                  "additionalProperties": false,
                  "properties": {
                    "union_string": {
                      "type": [
                        "string",
                        "null"
                      ]
                    }
                  },
                  "required": [
                    "union_string"
                  ],
                  "type": "object"
                }
              ]
            }
          },
          "required": [
            "tool_array_of_objects",
            "tool_fixed_const",
            "tool_mode",
            "tool_nested_object",
            "tool_optional_array_numbers",
            "tool_optional_string",
            "tool_required_array_strings",
            "tool_required_string",
            "tool_union_object"
          ],
          "type": "object"
        },
        "strict": true,
        "type": "function"
      }
    ]
    """).strip()

    assert actual == expected
