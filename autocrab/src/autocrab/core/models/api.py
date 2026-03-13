from typing import Literal, Union, List, Optional, Dict, Any
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Content Parts
# -----------------------------------------------------------------------------

class InputTextContentPart(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str

class OutputTextContentPart(BaseModel):
    type: Literal["output_text"] = "output_text"
    text: str

class InputImageSourceUrl(BaseModel):
    type: Literal["url"] = "url"
    url: str

class InputImageSourceBase64(BaseModel):
    type: Literal["base64"] = "base64"
    media_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"]
    data: str  # base64-encoded

InputImageSource = Union[InputImageSourceUrl, InputImageSourceBase64]

class InputImageContentPart(BaseModel):
    type: Literal["input_image"] = "input_image"
    source: InputImageSource

class InputFileSourceUrl(BaseModel):
    type: Literal["url"] = "url"
    url: str

class InputFileSourceBase64(BaseModel):
    type: Literal["base64"] = "base64"
    media_type: str  # MIME type
    data: str  # base64-encoded
    filename: Optional[str] = None

InputFileSource = Union[InputFileSourceUrl, InputFileSourceBase64]

class InputFileContentPart(BaseModel):
    type: Literal["input_file"] = "input_file"
    source: InputFileSource

ContentPart = Union[
    InputTextContentPart,
    OutputTextContentPart,
    InputImageContentPart,
    InputFileContentPart,
]

# -----------------------------------------------------------------------------
# Item Types (ItemParam)
# -----------------------------------------------------------------------------

MessageItemRole = Literal["system", "developer", "user", "assistant"]

class MessageItem(BaseModel):
    type: Literal["message"] = "message"
    role: MessageItemRole
    content: Union[str, List[ContentPart]]

class FunctionCallItem(BaseModel):
    type: Literal["function_call"] = "function_call"
    id: Optional[str] = None
    call_id: Optional[str] = None
    name: str
    arguments: str

class FunctionCallOutputItem(BaseModel):
    type: Literal["function_call_output"] = "function_call_output"
    call_id: str
    output: str

class ReasoningItem(BaseModel):
    type: Literal["reasoning"] = "reasoning"
    content: Optional[str] = None
    encrypted_content: Optional[str] = None
    summary: Optional[str] = None

class ItemReferenceItem(BaseModel):
    type: Literal["item_reference"] = "item_reference"
    id: str

ItemParam = Union[
    MessageItem,
    FunctionCallItem,
    FunctionCallOutputItem,
    ReasoningItem,
    ItemReferenceItem,
]

# -----------------------------------------------------------------------------
# Tool Definitions
# -----------------------------------------------------------------------------

class FunctionSpec(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class FunctionToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: FunctionSpec

ToolDefinition = FunctionToolDefinition

# -----------------------------------------------------------------------------
# Request Body
# -----------------------------------------------------------------------------

ToolChoiceAuto = Literal["auto", "none", "required"]

class ToolChoiceFunction(BaseModel):
    type: Literal["function"] = "function"
    function: Dict[str, str]

ToolChoice = Union[ToolChoiceAuto, ToolChoiceFunction]

class ReasoningConfig(BaseModel):
    effort: Optional[Literal["low", "medium", "high"]] = None
    summary: Optional[Literal["auto", "concise", "detailed"]] = None

class CreateResponseBody(BaseModel):
    model: str
    input: Union[str, List[ItemParam]]
    instructions: Optional[str] = None
    tools: Optional[List[ToolDefinition]] = None
    tool_choice: Optional[ToolChoice] = None
    stream: Optional[bool] = None
    max_output_tokens: Optional[int] = None
    max_tool_calls: Optional[int] = None
    user: Optional[str] = None
    
    # Phase 1 stubs
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    metadata: Optional[Dict[str, str]] = None
    store: Optional[bool] = None
    previous_response_id: Optional[str] = None
    reasoning: Optional[ReasoningConfig] = None
    truncation: Optional[Literal["auto", "disabled"]] = None

# -----------------------------------------------------------------------------
# Response Resource
# -----------------------------------------------------------------------------

ResponseStatus = Literal["in_progress", "completed", "failed", "cancelled", "incomplete"]

class OutputMessageItem(BaseModel):
    type: Literal["message"] = "message"
    id: str
    role: Literal["assistant"] = "assistant"
    content: List[OutputTextContentPart]
    status: Optional[Literal["in_progress", "completed"]] = None

class OutputFunctionCallItem(BaseModel):
    type: Literal["function_call"] = "function_call"
    id: str
    call_id: str
    name: str
    arguments: str
    status: Optional[Literal["in_progress", "completed"]] = None

class OutputReasoningItem(BaseModel):
    type: Literal["reasoning"] = "reasoning"
    id: str
    content: Optional[str] = None
    summary: Optional[str] = None

OutputItem = Union[OutputMessageItem, OutputFunctionCallItem, OutputReasoningItem]

class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int

class ApiError(BaseModel):
    code: str
    message: str

class ResponseResource(BaseModel):
    id: str
    object: Literal["response"] = "response"
    created_at: int
    status: ResponseStatus
    model: str
    output: List[OutputItem]
    usage: Usage
    error: Optional[ApiError] = None
