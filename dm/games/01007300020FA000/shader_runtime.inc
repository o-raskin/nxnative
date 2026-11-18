// ASTRAL CHAIN's original SMAA shaders, identified by their content hashes.
// Only their immutable c1 tuning constants change; programs, texture sampling,
// lookup tables and the three-pass SMAA algorithm remain the game's own.
// Edge threshold: original 0.1, High 0.05. Weight search bounds: original
// +/-31.8 pixels, High +/-63.8. Off suppresses edge detection, keeping the
// original pass/composition dependencies intact.
static void nvn_profile_shader_constants(const char *key, void *data, size_t len) {
    // DM_AC_C1DUMP=<key prefix>[,<key prefix>...] (diagnostic): logs the immutable constants (c1) of the named shaders as floats and hex words
    { static const char *dump; static int init; if(!init){init=1;dump=getenv("DM_AC_C1DUMP");}
      if(dump) { char list[512]; snprintf(list,sizeof list,"%s",dump); for(char *tok=strtok(list,",");tok;tok=strtok(NULL,",")) if(!strncmp(key,tok,strlen(tok))) {
          MLOG("[c1] %s len %zu",key,len); const uint32_t *w=data; for(size_t i=0;i<len/4&&i<96;i+=4) MLOG("[c1]   %3zu: %08x %08x %08x %08x | %g %g %g %g",i,w[i],i+1<len/4?w[i+1]:0,i+2<len/4?w[i+2]:0,i+3<len/4?w[i+3]:0,*(float*)&w[i],i+1<len/4?*(float*)&w[i+1]:0,i+2<len/4?*(float*)&w[i+2]:0,i+3<len/4?*(float*)&w[i+3]:0); } } }
    const char *mode = getenv("DM_AC_AA");
    if (!mode || !strcmp(mode, "default")) return;
    int high = !strcmp(mode, "high"), off = !strcmp(mode, "off");
    if (!high && !off) return;
    uint32_t *words = data;
    if (!strncmp(key, "8d7c664bb174a05f_", 17) && len >= 4) {
        if (words[0] != 0x3dcccccd) { MLOG("[RED] ASTRAL CHAIN SMAA edge constants differ from the verified shader"); return; }
        words[0] = off ? 0x7f7fffff : 0x3d4ccccd; // FLT_MAX or 0.05
        MLOG("ASTRAL CHAIN SMAA: %s edge threshold", off ? "off" : "High (0.05)");
    }
    if (high && !strncmp(key, "b56e3fc19366bac9_", 17) && len >= 24) {
        if (words[0] != 0xc1fe6666 || words[1] != 0x41fe6666) { MLOG("[RED] ASTRAL CHAIN SMAA search constants differ from the verified shader"); return; }
        words[0] = 0xc27f3333; words[1] = 0x427f3333; // -63.8, +63.8
        MLOG("ASTRAL CHAIN SMAA: High search bounds +/-63.8 pixels");
    }
}
