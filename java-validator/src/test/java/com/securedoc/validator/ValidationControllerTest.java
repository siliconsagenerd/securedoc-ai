package com.securedoc.validator;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class ValidationControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void healthReportsOk() throws Exception {
        mockMvc.perform(get("/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ok"))
                .andExpect(jsonPath("$.service").value("java-validator"));
    }

    @Test
    void validateAcceptsValidPdf() throws Exception {
        mockMvc.perform(post("/api/v1/validate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"filename\":\"report.pdf\",\"content_type\":\"application/pdf\",\"size_bytes\":1024}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.valid").value(true))
                .andExpect(jsonPath("$.checks.file_extension").value(true));
    }

    @Test
    void validateRejectsBadExtension() throws Exception {
        mockMvc.perform(post("/api/v1/validate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"filename\":\"run.exe\",\"content_type\":\"application/octet-stream\",\"size_bytes\":10}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.valid").value(false))
                .andExpect(jsonPath("$.checks.file_extension").value(false));
    }
}
