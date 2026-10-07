// vamp_host.cpp — host Vamp mínim per a AUTO CHORDS.
//
// Substitueix `sonic-annotator` (que arrossega Qt6/ICU/glib…): només enllaça
// amb libvamp-hostsdk (+ libsndfile per llegir el WAV) i escriu el CSV en el
// MATEIX format que `sonic-annotator -w csv --csv-one-file --csv-omit-filename`.
//
// Ús:
//   vamp_host --plugin <lib:plugin[:output]> --csv <sortida.csv> \
//             [--param id=valor]... <fitxer.wav>
//
// Exemples:
//   vamp_host --plugin nnls-chroma:chordino:simplechord --csv out.csv tema.wav
//   vamp_host --plugin qm-vamp-plugins:qm-tempotracker:tempo --csv t.csv tema.wav
//   vamp_host --plugin nnls-chroma:chordino:simplechord --param useHMM=0 ...
//
// Compilat amb -msse -msse2 (sense AVX; Q9400).
#include <vamp-hostsdk/PluginLoader.h>

#include <sndfile.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>

using namespace Vamp;
using namespace Vamp::HostExt;

static void ajuda() {
    fprintf(stderr,
            "Ús: vamp_host --plugin <lib:plugin[:output]> --csv <out.csv> "
            "[--param id=valor]... <fitxer.wav>\n");
}

int main(int argc, char **argv) {
    std::string pluginId, outNom, csvPath, wavPath;
    long step0 = 0, block0 = 0;
    std::map<std::string, float> params;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--plugin" && i + 1 < argc) {
            pluginId = argv[++i];
        } else if (a == "--csv" && i + 1 < argc) {
            csvPath = argv[++i];
        } else if (a == "--step" && i + 1 < argc) {
            step0 = atol(argv[++i]);
        } else if (a == "--block" && i + 1 < argc) {
            block0 = atol(argv[++i]);
        } else if (a == "--param" && i + 1 < argc) {
            std::string kv = argv[++i];
            size_t eq = kv.find('=');
            if (eq != std::string::npos)
                params[kv.substr(0, eq)] = (float)atof(kv.c_str() + eq + 1);
        } else if (a == "-h" || a == "--help") {
            ajuda();
            return 0;
        } else if (!a.empty() && a[0] != '-') {
            wavPath = a;
        }
    }
    if (pluginId.empty() || csvPath.empty() || wavPath.empty()) {
        ajuda();
        return 2;
    }

    // "vamp:lib:plugin:output" -> key "lib:plugin" + output "output"
    std::string id = pluginId;
    if (id.rfind("vamp:", 0) == 0) id = id.substr(5);
    std::vector<std::string> parts;
    size_t p = 0, q;
    while ((q = id.find(':', p)) != std::string::npos) {
        parts.push_back(id.substr(p, q - p));
        p = q + 1;
    }
    parts.push_back(id.substr(p));
    if (parts.size() >= 3) {
        outNom = parts.back();
        parts.pop_back();
    }
    std::string key = parts[0] + ":" + parts[1];

    // --- llegeix el WAV (float) ---
    SF_INFO info;
    memset(&info, 0, sizeof(info));
    SNDFILE *sf = sf_open(wavPath.c_str(), SFM_READ, &info);
    if (!sf) {
        fprintf(stderr, "no puc obrir %s: %s\n", wavPath.c_str(),
                sf_strerror(NULL));
        return 1;
    }
    int sr = info.samplerate;
    int ch = info.channels;
    sf_count_t n = info.frames;
    std::vector<float> dades((size_t)n * ch);
    sf_readf_float(sf, dades.data(), n);
    sf_close(sf);

    // --- carrega el plugin ---
    PluginLoader *loader = PluginLoader::getInstance();
    // NOTA: ADAPT_ALL inclou el PluginBufferingAdapter, que exigeix
    // step==block i trenca l'analisi del Segmentino (1 sol tros). Fem servi
    // nomes els adaptadors de domini d'entrada i de canals.
    Plugin *plug = loader->loadPlugin(key, sr,
        PluginLoader::ADAPT_INPUT_DOMAIN | PluginLoader::ADAPT_CHANNEL_COUNT);
    if (!plug) {
        fprintf(stderr, "no puc carregar el plugin '%s' (VAMP_PATH?)\n",
                key.c_str());
        return 1;
    }

    // output: el plugin calcula TOTS els outputs; ens quedem el que volem
    Plugin::OutputList outs = plug->getOutputDescriptors();
    int outIdx = 0;
    if (!outNom.empty()) {
        for (size_t i = 0; i < outs.size(); ++i)
            if (outs[i].identifier == outNom) outIdx = (int)i;
    }

    // paràmetres
    for (std::map<std::string, float>::iterator it = params.begin();
         it != params.end(); ++it)
        plug->setParameter(it->first, it->second);

    // --- inicialitza ---
    size_t step = step0 > 0 ? (size_t)step0 : plug->getPreferredStepSize();
    size_t block = block0 > 0 ? (size_t)block0 : plug->getPreferredBlockSize();
    if (step == 0) step = block;  // alguns plugins no donen step
    // (amb els adaptadors d'input/canals NO cal forcar step==block)
    if (!plug->initialise((size_t)ch, step, block)) {
        fprintf(stderr, "no puc inicialitzar el plugin '%s'\n", key.c_str());
        return 1;
    }

    // --- processa (blocs amb solapament step/block) ---
    Plugin::FeatureSet fs;
    // El plugin vol els canals SEPARATS (no intercalats): desem els blocs.
    std::vector<std::vector<float> > buf(ch, std::vector<float>(block));
    std::vector<float *> canals(ch);
    for (int c = 0; c < ch; ++c) canals[c] = buf[c].data();
    sf_count_t pos = 0;
    while (pos + (sf_count_t)block <= n) {
        for (size_t i = 0; i < block; ++i)
            for (int c = 0; c < ch; ++c)
                buf[c][i] = dades[((size_t)pos + i) * ch + c];
        RealTime ts = RealTime::frame2RealTime(pos, sr);
        Plugin::FeatureSet f = plug->process(canals.data(), ts);
        for (Plugin::FeatureSet::iterator it = f.begin(); it != f.end(); ++it)
            fs[it->first].insert(fs[it->first].end(), it->second.begin(),
                                 it->second.end());
        pos += (sf_count_t)step;
    }
    Plugin::FeatureSet rest = plug->getRemainingFeatures();
    for (Plugin::FeatureSet::iterator it = rest.begin(); it != rest.end();
         ++it)
        fs[it->first].insert(fs[it->first].end(), it->second.begin(),
                             it->second.end());

    // --- escriu el CSV (mateix format que sonic-annotator) ---
    FILE *out = fopen(csvPath.c_str(), "w");
    if (!out) {
        fprintf(stderr, "no puc escriure %s\n", csvPath.c_str());
        return 1;
    }
    Plugin::FeatureList buit;
    Plugin::FeatureList &fl = fs.count(outIdx) ? fs[outIdx] : buit;
    {
        for (size_t i = 0; i < fl.size(); ++i) {
            const Plugin::Feature &f = fl[i];
            double ts = f.timestamp.sec + f.timestamp.nsec / 1e9;
            fprintf(out, "%.9f", ts);
            if (f.hasDuration)
                fprintf(out, ",%.9f",
                        f.duration.sec + f.duration.nsec / 1e9);
            for (size_t v = 0; v < f.values.size(); ++v)
                fprintf(out, ",%g", f.values[v]);
            if (!f.label.empty())
                fprintf(out, ",\"%s\"", f.label.c_str());
            fprintf(out, "\n");
        }
    }
    fclose(out);

    delete plug;
    return 0;
}
