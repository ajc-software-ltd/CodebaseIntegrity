// HLSL extraction fixture.
struct VS_INPUT {
    float3 pos : POSITION;
};

float4 main(VS_INPUT input) : SV_Position {
    return float4(input.pos, 1.0);
}
