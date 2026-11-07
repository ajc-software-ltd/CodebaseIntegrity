// GLSL extraction fixture.
struct Light {
    vec3 position;
};

vec3 shade(Light light, vec3 normal) {
    return light.position;
}
