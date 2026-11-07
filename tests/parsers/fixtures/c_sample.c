/* C extraction fixture: functions, structs, unions, enums, typedefs. */

typedef struct AudioDevice AudioDevice;

typedef struct {
    int sample_rate;
} AudioConfig;

struct Wave {
    float* data;
};

union Value {
    int i;
    float f;
};

enum Channel { LEFT, RIGHT };

static int audio_init(AudioConfig* config);
static int audio_init(void);

int audio_start(void) {
    return 0;
}

void audio_stop(void) {
}
