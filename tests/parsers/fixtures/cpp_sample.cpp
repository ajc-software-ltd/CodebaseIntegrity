// C++ extraction fixture: nested namespaces, classes, ctors/dtors,
// templates, overloads, inheritance, access modifiers.

namespace VulkanOne {
namespace Rendering {

class VulkanDevice;

class VulkanRenderer : public BaseRenderer, protected IFramed {
public:
    VulkanRenderer();
    ~VulkanRenderer();
    void initialize(const char* title);
    void shutdown();
    void begin_frame();
    void end_frame();
    bool present();
    bool present(int flags);
private:
    void helper();
    int frame_;
};

struct RenderSettings {
    int width;
};

enum class RenderMode { Solid, Wireframe };

template <typename T>
T clamp_value(T v) { return v; }

int free_function(int a);
int free_function(const char* s);

} // namespace Rendering
} // namespace VulkanOne
